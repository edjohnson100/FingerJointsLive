import math

import adsk.core
import adsk.fusion

from .options import DynamicSizeType, JointType, PlacementType, DogBoneStyle


def findOrthogonalUnitVectors(z):
    v = adsk.core.Vector3D.create(1, 0, 0)
    if v.isParallelTo(z):
        v = adsk.core.Vector3D.create(0, 1, 0)
    x = z.crossProduct(v)
    x.normalize()
    y = z.crossProduct(x)
    y.normalize()
    return x, y


class CoordinateSystem(object):
    def __init__(self, direction, body):
        """Creates a coordinate system where the z axis is in the given direction
        and the bounding box of the given body is centered around this axis"""
        # Define the axes of the coordinate system.
        if direction is None:
            # Auto-detect direction by finding the longest linear edge in the overlapping body
            max_len = -1
            for edge in body.edges:
                if edge.geometry.objectType == adsk.core.Line3D.classType():
                    start = edge.startVertex.geometry
                    end = edge.endVertex.geometry
                    length = start.distanceTo(end)
                    if length > max_len:
                        max_len = length
                        origin = start
                        zAxis = start.vectorTo(end)
            if max_len == -1:
                origin = adsk.core.Point3D.create(0, 0, 0)
                zAxis = adsk.core.Vector3D.create(0, 0, 1)
        elif isinstance(direction, adsk.fusion.BRepEdge):
            origin = direction.startVertex.geometry
            zAxis = origin.vectorTo(direction.endVertex.geometry)
        else:
            assert(isinstance(direction, adsk.fusion.SketchLine))
            origin = direction.startSketchPoint.worldGeometry
            zAxis = origin.vectorTo(direction.endSketchPoint.worldGeometry)
        zAxis.normalize()
        xAxis, yAxis = findOrthogonalUnitVectors(zAxis)

        # Get a preliminary transformation (axis are correct but origin will be shifted later).
        preliminaryTransform = adsk.core.Matrix3D.create()
        preliminaryTransform.setWithCoordinateSystem(origin, xAxis, yAxis, zAxis)
        inversePreliminaryTransform = preliminaryTransform.copy()
        inversePreliminaryTransform.invert()

        # Find center of body's bounding box in local coordinates.
        temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        body_local = temporaryBRepManager.copy(body)
        temporaryBRepManager.transform(body_local, inversePreliminaryTransform)
        bb = body_local.boundingBox
        minx, miny, minz = bb.minPoint.asArray()
        maxx, maxy, maxz = bb.maxPoint.asArray()
        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2

        # Create the coordinate system with the correct origin
        origin = adsk.core.Point3D.create(cx, cy, minz)
        origin.transformBy(preliminaryTransform)
        self.transform = adsk.core.Matrix3D.create()
        self.transform.setWithCoordinateSystem(origin, xAxis, yAxis, zAxis)
        self.inverseTransform = self.transform.copy()
        self.inverseTransform.invert()

    def transformToLocalCoordinates(self, body):
        temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        temporaryBRepManager.transform(body, self.inverseTransform)

    def transformToGlobalCoordinates(self, body):
        temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        temporaryBRepManager.transform(body, self.transform)


def createBox(x, y, z, length, width, height):
    centerPoint = adsk.core.Point3D.create(x, y, z)
    lengthDirection = adsk.core.Vector3D.create(1, 0, 0)
    widthDirection = adsk.core.Vector3D.create(0, 1, 0)
    return adsk.core.OrientedBoundingBox3D.create(centerPoint, lengthDirection, widthDirection, length, width, height)


def _gapCompensationTransform(length, width, gapToPart, scaleX=True, scaleY=True):
    """Scale-based approximation of a uniform gapToPart standoff (see createToolBody's comment
    on why scaling is only exact when the intersection is square). scaleX/scaleY let a caller
    exclude an axis, though nothing currently does - both dovetail tools use the same uniform
    scale (see _finalizeDovetailToolBody) since the notch tool is built as the finger tool's
    exact complement and an asymmetric per-axis scale would break that relationship."""
    epsilon = 0.00001 # avoid rounding issues with floats
    scaleFactorX = (length + 2*gapToPart) / length if scaleX else 1.0
    scaleFactorY = (width + 2*gapToPart) / width if scaleY else 1.0
    if scaleX and scaleY:
        # Note that we have to scale in x and y direction with the same factor because the axes
        # may not be aligned with the axis of the intersection.
        scaleFactorX = scaleFactorY = max(scaleFactorX, scaleFactorY)
    if (scaleX and scaleFactorX <= epsilon) or (scaleY and scaleFactorY <= epsilon):
        # A large enough negative gapToPart collapses or inverts the tool body - reject rather
        # than pass invalid geometry on to the boolean cut.
        return None
    transform = adsk.core.Matrix3D.create()
    transform.setWithArray([scaleFactorX, 0,            0, 0,
                            0,            scaleFactorY, 0, 0,
                            0,            0,            1, 0,
                            0,            0,            0, 1])
    return transform


def _halfSpaceBox(pivotPoint, normal, size):
    """A large box (side length `size`, which the caller must size larger than whatever this
    will be intersected with) whose near face is the plane through pivotPoint perpendicular to
    normal, extending away from pivotPoint in the +normal direction. Used to trim a slice's flat
    Z-boundary into an angled dovetail wall via boolean intersection."""
    n = normal.copy()
    n.normalize()
    helper = adsk.core.Vector3D.create(1, 0, 0)
    if abs(helper.dotProduct(n)) > 0.9:
        helper = adsk.core.Vector3D.create(0, 1, 0)
    u = n.crossProduct(helper)
    u.normalize()
    v = n.crossProduct(u)
    v.normalize()
    # u x v == n, so an OrientedBoundingBox3D built from (u, v) has its "height" axis along
    # normal - matching createBox()'s (x, y) -> z convention above.
    center = pivotPoint.copy()
    offset = n.copy()
    offset.scaleBy(size / 2)
    center.translateBy(offset)
    obb = adsk.core.OrientedBoundingBox3D.create(center, u, v, size, size, size)
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    return temporaryBRepManager.createBox(obb)


def _addDogBones(temporaryBRepManager, targetBody, slices, minz, maxz, dogBoneInfo, radius, clearance, transform):
    """Unions one relief cylinder into targetBody for every interior wall x floor corner
    identified by dogBoneInfo (see _computeDogBoneAxisInfo), skipping walls that coincide with
    this body's own true physical edge (dogBoneInfo['rowStartIsEdge']/['rowEndIsEdge'] - NOT
    simply "wall equals minz/maxz", which only means "the row's own boundary", not necessarily a
    real edge - see _computeDogBoneAxisInfo for why those can differ for an interior/T-junction
    joint like a shelf mortised into the middle of a wall). Called after targetBody's final clip
    against the real overlap and its gapToPart transform - dog bones are an additive bulge, so
    unlike the dovetail wedges (which trim before the clip) they must be added after it or the
    clip would cut the bulge right back off. Cylinder positions are transformed by `transform`
    (the same gapToPart matrix already baked into targetBody) so a relief stays visually attached
    to its wall even when gapToPart is nonzero; the radius itself is left unscaled so it always
    matches the entered bit diameter exactly.

    Each circle's center is NOT placed on the corner point itself - it's inset along the 45deg
    bisector, into the pocket, by (radius - clearance). At exactly radius, the circle's edge
    would just touch the corner; pulling the center in a bit closer than that pushes the circle
    slightly past the corner instead, so it unambiguously clears it rather than leaving a
    borderline (and possibly floating-point-fragile) exact tangent. `clearance` is clamped so it
    can never push the inset negative (center jumping past the corner to the wrong side)."""
    epsilon = 0.00001
    diag = 1 / math.sqrt(2)
    inset = max(0.0, radius - clearance) * diag
    openMin, openMax = dogBoneInfo['openMin'], dogBoneInfo['openMax']
    floorAxisIsX = dogBoneInfo['floorAxisIsX']
    rowStartIsEdge = dogBoneInfo['rowStartIsEdge']
    rowEndIsEdge = dogBoneInfo['rowEndIsEdge']

    def makePoint(floorVal, openVal, zVal):
        if floorAxisIsX:
            return adsk.core.Point3D.create(floorVal, openVal, zVal)
        else:
            return adsk.core.Point3D.create(openVal, floorVal, zVal)

    # rowDir/floorDir each say which way the pocket (the material being cut away) lies relative
    # to that wall - +1 if it's on the +axis side of the wall, -1 if on the -axis side - so the
    # corner's 45deg bisector, pointing into the pocket, is (rowDir, floorDir)/sqrt(2).
    walls = []
    for (sliceCenterStart, sliceThickness) in slices:
        start = minz + sliceCenterStart
        end = start + sliceThickness
        if not (rowStartIsEdge and start <= minz + epsilon):
            walls.append((start, 1))
        if not (rowEndIsEdge and end >= maxz - epsilon):
            walls.append((end, -1))

    for wallZ, rowDir in walls:
        for floorVal, floorDir in dogBoneInfo['floors']:
            cornerZ = wallZ + rowDir * inset
            cornerFloor = floorVal + floorDir * inset
            pointOne = makePoint(cornerFloor, openMin, cornerZ)
            pointTwo = makePoint(cornerFloor, openMax, cornerZ)
            pointOne.transformBy(transform)
            pointTwo.transformBy(transform)
            cylinder = temporaryBRepManager.createCylinderOrCone(pointOne, radius, pointTwo, radius)
            if cylinder is not None:
                temporaryBRepManager.booleanOperation(targetBody, cylinder, adsk.fusion.BooleanTypes.UnionBooleanType)


def _dovetailDepthIsX(overlapLocalBB, originalBody, coordinateSystem):
    """Picks which of the overlap's two non-row axes (x, y) is the dovetail's taper/depth
    axis, using the same "which axis is fully open against the original body" test as
    _computeDogBoneAxisInfo (see its docstring) instead of comparing raw sizes. The axis
    where originalBody's own bound matches the overlap's bound on both sides is the plunge
    axis - a bit passes straight through it, e.g. panel thickness on an ordinary corner
    joint - and that axis is never the taper axis; the OTHER non-row axis is, regardless of
    which one happens to be numerically smaller.

    This distinction is invisible for a corner joint, where the taper axis also happens to
    be a small panel thickness, so "smaller wins" looks right there. It breaks for a
    coplanar/inline splice: the plunge axis is still the thin panel thickness, but the true
    taper axis is the (much larger) splice overlap width - a plain size comparison picks
    the thin plunge axis instead and tapers the wrong way.

    Falls back to the old smaller-wins comparison if originalBody's bounds don't cleanly
    identify a single open axis (neither side matches, or both do)."""
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    bodyLocal = temporaryBRepManager.copy(originalBody)
    coordinateSystem.transformToLocalCoordinates(bodyLocal)
    bodyBB = bodyLocal.boundingBox

    epsilon = 0.00001
    omin, omax = overlapLocalBB.minPoint, overlapLocalBB.maxPoint
    bmin, bmax = bodyBB.minPoint, bodyBB.maxPoint

    xOpen = abs(bmin.x - omin.x) <= epsilon and abs(bmax.x - omax.x) <= epsilon
    yOpen = abs(bmin.y - omin.y) <= epsilon and abs(bmax.y - omax.y) <= epsilon

    if xOpen != yOpen:
        return yOpen
    return (omax.x - omin.x) <= (omax.y - omin.y)


def _dovetailCombGeometry(body, inputs, coordinateSystem):
    """Shared setup for the dovetail comb builders: the depth axis/extent, row extent, and
    angle trig, all derived once from the (already-local-coordinates) overlap body so the
    finger comb and the full row slab agree exactly on bounds."""
    bb = body.boundingBox
    minx, miny, minz = bb.minPoint.asArray()
    maxx, maxy, maxz = bb.maxPoint.asArray()
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    slack = 1
    length = maxx - minx + slack
    width = maxy - miny + slack
    size = maxz - minz

    depthIsX = _dovetailDepthIsX(bb, inputs.body0, coordinateSystem)
    if depthIsX:
        Amin, Amax = minx, maxx
        wCenter = cy
    else:
        Amin, Amax = miny, maxy
        wCenter = cx

    angle = inputs.dovetailAngle.value
    # reverseTaper swaps which face of the depth axis (Amin vs. Amax) ends up wide vs. narrow.
    # This needs BOTH the wedge normal's sign flipped AND the taper's anchor point moved from
    # Amin to Amax - sign alone is not enough. The working (non-reversed) formula keeps the
    # wedge's own "-sinAngle" term negative while anchoring at Amin; naively flipping just
    # sinAngle's sign while leaving the anchor at Amin cancels that back to +sinAngle with an
    # Amin anchor, which is EXACTLY the very first no-op bug this file had (a wedge that only
    # ever trims the oversized slack region and never touches the true footprint) - confirmed
    # by hand, this is why that attempt visibly "squared up" the joint instead of reversing it.
    # Moving the anchor to Amax at the same time makes it a real (non-degenerate), genuinely
    # reversed cut instead. This is a single global choice, so it flips ALL teeth in the comb
    # together - since the notch tool is always the finger comb's exact complement (see
    # createToolBodies), flipping it still produces fully mating, interlocking geometry; it
    # only mirrors which face looks wide vs. narrow. The "right" direction depends on physical
    # context (corner vs. inline splice, which body is body0/body1, direction-edge orientation)
    # that the geometry can't infer, hence a user-facing toggle rather than a hardcoded choice.
    taperSign = -1 if inputs.reverseTaper else 1
    Aref = Amax if inputs.reverseTaper else Amin
    return {
        'minz': minz, 'cx': cx, 'cy': cy, 'length': length, 'width': width, 'size': size,
        'depthIsX': depthIsX, 'Amin': Amin, 'Amax': Amax, 'wCenter': wCenter, 'Aref': Aref,
        'tanAngle': math.tan(angle), 'cosAngle': math.cos(angle),
        'sinAngle': math.sin(angle) * taperSign,
    }


def _computeDogBoneAxisInfo(overlapLocalBB, originalBody, coordinateSystem):
    """Classifies the overlap's two non-row local axes (x, y) for dog-bone placement on one of
    the two joined bodies. One axis should be fully "open" - originalBody's own bounding box
    matches the overlap's bounds on both sides there, meaning that axis is the panel's true
    thickness, already open on both faces (a bit plunging clear through the board, same as a
    box-joint cut always is along the row/z axis). The other axis is the "floor" axis: wherever
    originalBody's own bound is set by the *other* body's extent rather than its own, that's
    where a round bit's reach stops and creates a new interior corner - each such side (min
    and/or max) becomes one (value, direction) entry in the returned 'floors' list, where
    direction is +1 if the pocket lies on the +floor-axis side of that boundary (a min-side
    floor) or -1 if on the -floor-axis side (a max-side floor) - see _addDogBones, which uses
    this sign to inset each relief circle's center into the pocket along the corner's bisector.

    Returns None when the overlap doesn't look like a plain rectangular corner between two flat
    panels (both axes open, or both axes have a floor side) - dog-bone placement is skipped for
    that body rather than guessing at more complex geometry (e.g. beveled or stepped edges).

    Also classifies the row axis (z) the same way, as 'rowStartIsEdge'/'rowEndIsEdge': whether
    minz/maxz - the row's own boundary - coincides with THIS body's own true physical edge there.
    For a box corner (panels modeled edge-to-edge) it usually does, so the outermost tooth's
    end needs no relief - same boundary extendStartIfNeeded/extendEndIfNeeded treat specially.
    But for an interior/T-junction joint (e.g. a shelf mortised into the middle of a wall), minz/
    maxz is just where the small overlap happens to end, not a real edge of the (much larger)
    wall - that boundary still needs relief like any other interior wall. This can differ per
    body in the same joint: the finger side's outermost tooth may sit flush with its own true
    edge while the notch side's corresponding cut, on the other body, does not."""
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    bodyLocal = temporaryBRepManager.copy(originalBody)
    coordinateSystem.transformToLocalCoordinates(bodyLocal)
    bodyBB = bodyLocal.boundingBox

    epsilon = 0.00001
    omin, omax = overlapLocalBB.minPoint, overlapLocalBB.maxPoint
    bmin, bmax = bodyBB.minPoint, bodyBB.maxPoint

    xMinOpen = abs(bmin.x - omin.x) <= epsilon
    xMaxOpen = abs(bmax.x - omax.x) <= epsilon
    yMinOpen = abs(bmin.y - omin.y) <= epsilon
    yMaxOpen = abs(bmax.y - omax.y) <= epsilon
    xOpen = xMinOpen and xMaxOpen
    yOpen = yMinOpen and yMaxOpen

    if xOpen == yOpen:
        # Both fully open (no interior corner here at all) or neither is (a shape more complex
        # than a plain rectangular corner) - either way there's no single well-defined floor axis.
        return None

    if xOpen:
        openMin, openMax = omin.x, omax.x
        floorAxisIsX = False
        floorMinOpen, floorMaxOpen, floorMin, floorMax = yMinOpen, yMaxOpen, omin.y, omax.y
    else:
        openMin, openMax = omin.y, omax.y
        floorAxisIsX = True
        floorMinOpen, floorMaxOpen, floorMin, floorMax = xMinOpen, xMaxOpen, omin.x, omax.x

    floors = []
    if not floorMinOpen:
        floors.append((floorMin, 1))
    if not floorMaxOpen:
        floors.append((floorMax, -1))
    if not floors:
        return None

    rowStartIsEdge = abs(bmin.z - omin.z) <= epsilon
    rowEndIsEdge = abs(bmax.z - omax.z) <= epsilon

    return {
        'openMin': openMin, 'openMax': openMax,
        'floorAxisIsX': floorAxisIsX, 'floors': floors,
        'rowStartIsEdge': rowStartIsEdge, 'rowEndIsEdge': rowEndIsEdge,
    }


def _buildDovetailComb(slices, geom):
    """Builds the raw tapered comb (union of wedge-trimmed slices) for one dimension list -
    NOT yet intersected with the real overlap body and with no gapToPart applied. Every tooth
    is at its nominal (box-joint) width at the depth axis's anchor face (geom['Aref'], normally
    Amin but Amax when inputs.reverseTaper is set) and narrows towards the opposite face, like
    a physical dovetail router bit narrowing from shank to tip. Returns None if a
    self-intersection guard trips (see below).

    This builds ONLY the fingerToolDimensions-style comb. createToolBodies never calls this a
    second time for notchToolDimensions with some mirrored/flipped variant - that was tried
    (twice) and is mathematically impossible to get right this way: a wall trimmed via a
    half-space wedge is only a *real* cut (not a no-op that just trims the oversized slack
    region and leaves the true footprint untouched) if its trajectory increases with depth for
    a start wall, or decreases for an end wall - that's forced, not a convention. But two combs
    built independently need their shared boundary walls to be numerically IDENTICAL functions
    of depth to mate, and an increasing function can't equal a decreasing one except at one
    depth. So instead, createToolBodies builds the notch comb as this comb's exact geometric
    complement within the full row slab - see createToolBodies for why that's the only
    approach that guarantees matching walls by construction."""
    minz, cx, cy = geom['minz'], geom['cx'], geom['cy']
    length, width, size = geom['length'], geom['width'], geom['size']
    depthIsX, Amin, wCenter, Aref = geom['depthIsX'], geom['Amin'], geom['wCenter'], geom['Aref']
    tanAngle, cosAngle, sinAngle = geom['tanAngle'], geom['cosAngle'], geom['sinAngle']
    depthExtent = geom['Amax'] - Amin

    # Sanity-check: each cut interval's own two walls converge as depth increases from Amin to
    # Amax (that convergence is what makes the cut a real, non-degenerate taper rather than a
    # no-op - see this function's docstring). If a cut's nominal thickness is narrower than
    # twice the maximum convergence (depthExtent * tanAngle per side), its two walls cross
    # before reaching the far face - a self-intersecting/bowtie cut, which would also pinch the
    # complementary tooth (built from this comb in createToolBodies) to zero width there.
    epsilon = 0.00001
    for (sliceCenterStart, sliceThickness) in slices:
        if sliceThickness - 2 * depthExtent * tanAngle <= epsilon:
            return None

    def makePoint(aVal, zVal):
        if depthIsX:
            return adsk.core.Point3D.create(aVal, wCenter, zVal)
        else:
            return adsk.core.Point3D.create(wCenter, aVal, zVal)

    if depthIsX:
        nStart = adsk.core.Vector3D.create(-sinAngle, 0, cosAngle)
        nEnd = adsk.core.Vector3D.create(-sinAngle, 0, -cosAngle)
    else:
        nStart = adsk.core.Vector3D.create(0, -sinAngle, cosAngle)
        nEnd = adsk.core.Vector3D.create(0, -sinAngle, -cosAngle)

    bigSize = 20 * (length + width + size)

    # A tapered wall, unlike createToolBody's flat ones, drifts away from the row's true
    # boundary (Z = minz or minz+size) as depth moves away from Aref - if we tapered the
    # outermost teeth's true-edge wall too, it would leave either a proud sliver or an
    # undercut notch right at the panel's real edge. Instead, extend just that wall's
    # reference position outward by more than the taper can ever drift (plus a small buffer),
    # so the tapered wall stays outside the panel at every depth and the final intersection
    # with the real overlap body clips it back to a clean, untapered edge.
    edgeEpsilon = 0.0001
    edgeBuffer = depthExtent * tanAngle + 0.1
    numSlices = len(slices)

    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    targetBody = None
    for i, (sliceCenterStart, sliceThickness) in enumerate(slices):
        start = minz + sliceCenterStart
        end = start + sliceThickness
        if i == 0 and sliceCenterStart <= edgeEpsilon:
            start -= edgeBuffer
        if i == numSlices - 1 and sliceCenterStart + sliceThickness >= size - edgeEpsilon:
            end += edgeBuffer

        box = createBox(cx, cy, (start + end) / 2, length, width, end - start)
        sliceBody = temporaryBRepManager.createBox(box)

        pivotStart = makePoint(Aref, start)
        startWedge = _halfSpaceBox(pivotStart, nStart, bigSize)
        temporaryBRepManager.booleanOperation(sliceBody, startWedge, adsk.fusion.BooleanTypes.IntersectionBooleanType)

        pivotEnd = makePoint(Aref, end)
        endWedge = _halfSpaceBox(pivotEnd, nEnd, bigSize)
        temporaryBRepManager.booleanOperation(sliceBody, endWedge, adsk.fusion.BooleanTypes.IntersectionBooleanType)

        if targetBody is None:
            targetBody = sliceBody
        else:
            temporaryBRepManager.booleanOperation(targetBody, sliceBody, adsk.fusion.BooleanTypes.UnionBooleanType)

    return targetBody


def _finalizeDovetailToolBody(rawComb, body, inputs, geom):
    """Shared final steps for both the finger comb and its notch complement: intersect with
    the real overlap body (clipping oversized slack and the edge-buffer overshoot down to the
    panel's true footprint) and apply the gapToPart standoff. Both tools get the same uniform
    bounding-box scale (not a wedge-offset) for gapToPart - see createToolBodies for why: the
    notch comb only exists as this comb's complement, so anything baked asymmetrically into one
    comb's wedge placement would break that complement relationship instead of adding a clean
    standoff to both."""
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    temporaryBRepManager.booleanOperation(rawComb, body, adsk.fusion.BooleanTypes.IntersectionBooleanType)

    gapToPart = inputs.gapToPart.value
    transform = _gapCompensationTransform(geom['length'], geom['width'], gapToPart)
    if transform is None:
        return None
    temporaryBRepManager.transform(rawComb, transform)
    return rawComb


def createToolBody(body, slices, inputs, debug=False):
    bb = body.boundingBox
    minx, miny, minz = bb.minPoint.asArray()
    maxx, maxy, maxz = bb.maxPoint.asArray()
    cx = (minx + maxx) / 2
    cy = (miny + maxy) / 2
    # To avoid issues with rounding, we add 1cm of slack.
    slack = 1
    length = maxx - minx + slack
    width = maxy - miny + slack

    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    targetBody = None
    for (sliceCenterStart, sliceThickness) in slices:
        box = createBox(cx, cy, minz + sliceCenterStart + sliceThickness/2, length, width, sliceThickness)
        sliceBody = temporaryBRepManager.createBox(box)
        if targetBody is None:
            targetBody = sliceBody
        else:
            temporaryBRepManager.booleanOperation(targetBody, sliceBody, adsk.fusion.BooleanTypes.UnionBooleanType)

    if debug:
        app = adsk.core.Application.get()
        root = app.activeProduct.rootComponent
        feature = root.features.baseFeatures.add()
        feature.startEdit()
        root.bRepBodies.add(targetBody, feature)
        feature.finishEdit()
        feature = root.features.baseFeatures.add()
        feature.startEdit()
        root.bRepBodies.add(body, feature)
        feature.finishEdit()

    temporaryBRepManager.booleanOperation(targetBody, body, adsk.fusion.BooleanTypes.IntersectionBooleanType)

    # Scale up tool body, so its length and width are increased by the gap we want to leave to the other part.
    # The correct way to do so would be to compute an offset. Scaling works if the intersection is a square but
    # will otherwise have a too large gap on one side.
    gapToPart = inputs.gapToPart.value
    transform = _gapCompensationTransform(length, width, gapToPart)
    if transform is None:
        return None
    temporaryBRepManager.transform(targetBody, transform)

    return targetBody


def createBodyFromOverlap(body0, body1):
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    overlapBody = temporaryBRepManager.copy(body0)
    temporaryBRepManager.booleanOperation(overlapBody, body1, adsk.fusion.BooleanTypes.IntersectionBooleanType)
    return overlapBody


# --- Manual butt-joint closing ---
# The user explicitly picks the face to extend (or an edge/vertex on it, since it's
# often tucked against the neighboring body and hard to click directly) and a target
# face to extend to. No guessing about which body/face/direction is involved.

def resolveSourceFace(entity):
    """Resolves a user selection (BRepFace, BRepEdge, or BRepVertex) down to the planar
    face to extend: the face itself, or - among the faces touching the selected edge or
    vertex - the smallest planar one (the true end-cap face is reliably the smallest
    face touching any point on it)."""
    if isinstance(entity, adsk.fusion.BRepFace):
        candidates = [entity]
    elif isinstance(entity, adsk.fusion.BRepEdge):
        candidates = list(entity.faces)
    elif isinstance(entity, adsk.fusion.BRepVertex):
        candidates = list(entity.faces)
    else:
        return None
    planarFaces = [f for f in candidates if f.geometry.objectType == adsk.core.Plane.classType()]
    if not planarFaces:
        return None
    return min(planarFaces, key=lambda f: f.area)


def getFaceOutwardNormal(face):
    """The face's true outward-oriented normal (respecting the face's own parametric
    orientation), rather than an approximation from bounding-box geometry."""
    point = face.pointOnFace
    success, normal = face.evaluator.getNormalAtPoint(point)
    if not success:
        raise RuntimeError("Could not evaluate the face's normal.")
    normal.normalize()
    return normal


def extensionLengthToFace(sourceFace, direction, targetFace, margin=0.0):
    """Exact distance from sourceFace's plane to targetFace's plane along `direction`.
    Returns a value <= 0 if targetFace is on the wrong side (not in the direction we'd
    extend)."""
    vector = sourceFace.pointOnFace.vectorTo(targetFace.pointOnFace)
    distance = vector.dotProduct(direction)
    if distance <= 0:
        return distance
    return distance + margin


# --- Standalone Dog Bone operation ---
# Applied as a post-process to an already-cut body's real B-Rep topology, rather than baked
# into finger-joint generation like the (now unused) _addDogBones/_computeDogBoneAxisInfo
# above. On real topology a corner is bounded exactly where its edge's own vertices are, so
# unlike the old bounding-box-based model there's no separate "is this boundary the body's
# true edge, or just where a synthetic overlap region happened to end" question to resolve -
# every edge enumerateDogBoneCandidates finds is, by construction, a real edge of real
# geometry.

def detectPlungeAxis(body):
    """Picks the body's global plunge/cutting axis (the router bit's rotation/travel
    direction) as whichever bounding-box extent is smallest - generalizes
    _dovetailCombGeometry's depthIsX heuristic (which only chooses between two axes because
    its third is already fixed as the joint direction) to all three axes. Assumes the body
    is reasonably axis-aligned globally, true for typical flat CNC panels; Face selection
    mode exists for bodies where that assumption doesn't hold."""
    bb = body.boundingBox
    dx = bb.maxPoint.x - bb.minPoint.x
    dy = bb.maxPoint.y - bb.minPoint.y
    dz = bb.maxPoint.z - bb.minPoint.z
    if dx <= dy and dx <= dz:
        return adsk.core.Vector3D.create(1, 0, 0)
    elif dy <= dz:
        return adsk.core.Vector3D.create(0, 1, 0)
    else:
        return adsk.core.Vector3D.create(0, 0, 1)


def classifyEdgeConcavity(edge, face1, face2):
    """Classifies whether edge (shared by planar face1/face2) is a concave (reflex - a
    dogbone candidate) or convex corner of the solid.

    Deliberately does NOT use an edge-tangent-based test (e.g. comparing tangent direction
    to the two face normals' cross product): BRepEdge.startVertex/endVertex ordering is
    topological, not guaranteed to correlate with any consistent winding relative to the
    faces, so a tangent-orientation-dependent sign test can silently flip on some corners
    and not others.

    Instead, a plane-side test needing no edge orientation at all: take a point P on the
    edge, and check which side of face1's plane face2's interior sample point lies on. If
    face2 is on the *outward* side of face1 (in the direction of face1's own outward
    normal), the solid wraps around more than 180 degrees at this edge - concave/reflex,
    needs a dogbone. If face2 is on the inward side, the corner is convex (an ordinary
    corner, not a candidate). Cross-checked symmetrically with face1 against face2's plane;
    disagreement means an ambiguous/degenerate pair, skipped rather than guessed at."""
    epsilon = 0.00001
    n1 = getFaceOutwardNormal(face1)
    n2 = getFaceOutwardNormal(face2)
    p = edge.startVertex.geometry
    d1 = p.vectorTo(face2.pointOnFace).dotProduct(n1)
    d2 = p.vectorTo(face1.pointOnFace).dotProduct(n2)
    if abs(d1) <= epsilon or abs(d2) <= epsilon:
        return 'flat'
    if (d1 > 0) != (d2 > 0):
        return 'flat'
    return 'concave' if d1 > 0 else 'convex'


def angleBetweenFaces(face1, face2):
    """The angle (radians) between two planar faces' outward normals - independent of
    classifyEdgeConcavity's plane-side test: a convex and a concave 90-degree corner both
    give the same 90-degree angle here, only the plane-side test's sign distinguishes them."""
    n1 = getFaceOutwardNormal(face1)
    n2 = getFaceOutwardNormal(face2)
    dot = max(-1.0, min(1.0, n1.dotProduct(n2)))
    return math.acos(dot)


def _measureFaceExtentFromEdge(face, edge, plungeAxis):
    """Measures how far `face`'s own geometry extends away from `edge`, in the in-plane
    direction perpendicular to the edge (i.e. perpendicular to plungeAxis, since candidate
    edges always run parallel to it) - a robust proxy for "how long is this wall" that
    doesn't assume face's boundary is a simple rectangle with one clean "far edge" to
    measure against. A kerf-compensation sliver artifact (see enumerateDogBoneCandidates)
    is often wedge-shaped rather than rectangular, so it may have zero or several edges
    running parallel to the plunge axis - walking edges looking for exactly one was tried
    first and does not reliably catch these; measuring every vertex's own position instead
    works regardless of how many edges bound the face.

    inPlaneDir = plungeAxis x face's own outward normal is perpendicular to both, so it lies
    within face's plane and is perpendicular to the edge - exactly the direction a wall
    "extends away from its corner" in the cross-section plane the dogbone offset itself
    lives in."""
    epsilon = 0.00001
    normal = getFaceOutwardNormal(face)
    inPlaneDir = plungeAxis.crossProduct(normal)
    if inPlaneDir.length <= epsilon:
        return None
    inPlaneDir.normalize()

    edgePoint = edge.startVertex.geometry
    maxExtent = 0.0
    for vertex in face.vertices:
        vector = edgePoint.vectorTo(vertex.geometry)
        extent = abs(vector.dotProduct(inPlaneDir))
        if extent > maxExtent:
            maxExtent = extent
    return maxExtent


def measureAdjacentWallLength(edge, face, plungeAxis):
    """Measures how long `face` (one wall of a dog bone corner) runs, for Long Side/Short
    Side style's per-corner "which adjacent wall is longer" comparison. Finds face's other
    edge that also runs parallel to plungeAxis (the wall's "far edge", as opposed to `edge`
    itself, the near/corner edge) and measures the perpendicular distance between them - for
    a simple rectangular wall face there's exactly one such far edge.

    Returns None when that's not true (zero or multiple parallel candidate edges found) - a
    non-rectangular wall (stepped/curved boundary, or one already relieved by a nearby dog
    bone) can produce this - so computeDogBoneOffset can fall back to Corner style for that
    one corner instead of guessing."""
    epsilon = 0.00001
    axisToleranceCos = math.cos(math.radians(1))
    edgeStart = edge.startVertex.geometry
    edgeEnd = edge.endVertex.geometry

    def isSameEdge(other):
        # Geometric coincidence, not object identity - proxy objects returned by repeated
        # API property access aren't guaranteed to be comparable with ==.
        otherStart = other.startVertex.geometry
        otherEnd = other.endVertex.geometry
        direct = edgeStart.distanceTo(otherStart) <= epsilon and edgeEnd.distanceTo(otherEnd) <= epsilon
        swapped = edgeStart.distanceTo(otherEnd) <= epsilon and edgeEnd.distanceTo(otherStart) <= epsilon
        return direct or swapped

    farEdges = []
    for candidateEdge in face.edges:
        if candidateEdge.geometry.objectType != adsk.core.Line3D.classType():
            continue
        if isSameEdge(candidateEdge):
            continue
        tangent = candidateEdge.startVertex.geometry.vectorTo(candidateEdge.endVertex.geometry)
        if tangent.length <= epsilon:
            continue
        tangent.normalize()
        if abs(tangent.dotProduct(plungeAxis)) < axisToleranceCos:
            continue
        farEdges.append(candidateEdge)

    if len(farEdges) != 1:
        return None

    normal = getFaceOutwardNormal(face)
    inPlaneDir = plungeAxis.crossProduct(normal)
    if inPlaneDir.length <= epsilon:
        return None
    inPlaneDir.normalize()

    farPoint = farEdges[0].startVertex.geometry
    vector = edgeStart.vectorTo(farPoint)
    return abs(vector.dotProduct(inPlaneDir))


def enumerateDogBoneCandidates(body, plungeAxis, angleTolerance, minWallExtent=0.0):
    """Finds every edge on body that's a genuine interior (concave) corner suitable for a
    dogbone relief: a straight edge between two planar faces, running parallel to
    plungeAxis, whose two faces meet within angleTolerance (radians) of 90 degrees, and
    whose adjacent walls both extend at least minWallExtent away from the corner.

    The parallel-to-plunge-axis requirement isn't just a heuristic borrowed by analogy - two
    faces with mutually perpendicular normals intersect along a line parallel to the third
    orthogonal axis, so any genuine interior-corner edge of a 2.5D CNC-style cut necessarily
    runs parallel to the plunge axis; edges that don't are unrelated geometry (e.g. the
    panel's own outer silhouette), not candidates that merely failed some other check.

    minWallExtent guards against a real but unwanted artifact: negative-gap kerf
    compensation (see defineToolBodyDimensions' extendStartIfNeeded/extendEndIfNeeded) can
    leave a hairline sliver of geometry at a row boundary, only as wide as the kerf value
    (hundredths of a mm) rather than a real finger/notch (several mm) - concave and ~90
    degrees just like a genuine corner, but far too short for a relief circle to make any
    physical sense there. Callers should pass the bit radius: a wall shorter than the bit
    itself can't be usefully relieved regardless of why it's short."""
    epsilon = 0.00001
    axisToleranceCos = math.cos(math.radians(1))  # candidate edges must be parallel to plungeAxis within ~1 degree
    candidates = []
    for edge in body.edges:
        if edge.geometry.objectType != adsk.core.Line3D.classType():
            continue
        faces = list(edge.faces)
        if len(faces) != 2:
            continue
        face1, face2 = faces
        if face1.geometry.objectType != adsk.core.Plane.classType():
            continue
        if face2.geometry.objectType != adsk.core.Plane.classType():
            continue

        tangent = edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
        if tangent.length <= epsilon:
            continue
        tangent.normalize()
        if abs(tangent.dotProduct(plungeAxis)) < axisToleranceCos:
            continue

        if classifyEdgeConcavity(edge, face1, face2) != 'concave':
            continue
        if abs(angleBetweenFaces(face1, face2) - math.pi / 2) > angleTolerance:
            continue

        if minWallExtent > 0:
            extent1 = _measureFaceExtentFromEdge(face1, edge, plungeAxis)
            extent2 = _measureFaceExtentFromEdge(face2, edge, plungeAxis)
            if (extent1 is not None and extent1 < minWallExtent) or (extent2 is not None and extent2 < minWallExtent):
                continue

        candidates.append((edge, face1, face2))
    return candidates


def buildDogBoneCandidatesFromEdges(edges):
    """Builds dog bone candidates directly from user-picked edges (Edge selection mode),
    bypassing enumerateDogBoneCandidates' angle-tolerance auto-detection entirely - Edge
    mode exists precisely to let the user relieve corners that aren't close to 90 degrees,
    so no angle check applies here.

    Still rejects a picked edge outright if it isn't a genuine concave (reflex) corner at
    all, via the same classifyEdgeConcavity plane-side test enumerateDogBoneCandidates
    uses. This is NOT the angle heuristic Edge mode is meant to skip - a convex corner
    isn't a valid dog bone candidate under any style, full stop, so building a candidate
    from one wouldn't be "trusting the user's judgment," it would silently produce
    nonsensical geometry (the offset math assumes a concave pocket and drives the relief
    circle into material instead of away from it on a convex corner). This matters in
    practice: at the mouth of a finger-joint notch, the true concave "back of slot" edge
    and a convex edge one wall over sit right next to each other and are easy to
    misclick, especially at zero kerf comp where the finger's and slot's edges can be
    coincident.

    Also validates each picked edge is a straight line between exactly two planar faces,
    a hard requirement of the offset/cylinder math downstream, not a heuristic.

    Returns (candidates, skipped) - candidates is the usual list of (edge, face1, face2)
    tuples; skipped is a list of short human-readable reasons, one per picked edge that
    didn't qualify, for the caller to report back to the user rather than silently
    dropping picks."""
    candidates = []
    skipped = []
    for edge in edges:
        if edge.geometry.objectType != adsk.core.Line3D.classType():
            skipped.append("an edge that isn't straight")
            continue
        faces = list(edge.faces)
        if len(faces) != 2:
            skipped.append("an edge that isn't shared by exactly two faces")
            continue
        face1, face2 = faces
        if face1.geometry.objectType != adsk.core.Plane.classType() or face2.geometry.objectType != adsk.core.Plane.classType():
            skipped.append("an edge with a non-planar adjacent face")
            continue
        if classifyEdgeConcavity(edge, face1, face2) != 'concave':
            skipped.append("a convex or flat corner (not a valid dog bone candidate)")
            continue
        candidates.append((edge, face1, face2))
    return candidates, skipped


def computeDogBoneOffset(style, faceDir1, faceDir2, radius, clearance, interference, wallLength1=None, wallLength2=None):
    """Computes the 3D offset vector (from the true corner point - any point on the
    candidate edge, since faceDir1/faceDir2 are constant along the whole edge for planar
    faces) to a relief circle's center, for the given style. faceDir1/faceDir2 are the two
    adjacent faces' outward normals: already in-plane and perpendicular to the edge's
    tangent for planar faces (no extra projection needed), and they double as the two
    "into the pocket" wall directions the offset is built from.

    Corner: center inset along the bisector by (radius - clearance) - at exactly `radius`
    the circle's edge would just touch the corner; clearance pulls the center a bit closer
    so the circle pushes slightly past the corner instead, unambiguously clearing it rather
    than leaving a borderline (and floating-point-fragile) exact tangent.

    Minimal Corner: the mirror image - center pushed OUT along the same bisector by
    (radius + interference), so the circle's edge falls short of the corner by exactly
    `interference` (a little remaining material forces a tight fit, with a smaller/less
    visually obvious relief than Corner style).

    Long Side / Short Side: a single-wall offset (not diagonal) - offset along only
    faceDir1 or faceDir2 puts the circle's center exactly on the OTHER wall's own plane
    (its component along that wall's normal is zero), so the circle straddles that other
    wall symmetrically and bulges out along it; meanwhile it clears the CHOSEN wall (the
    one the offset runs along) by exactly `clearance`, same as Corner style does relative
    to a single wall. Confirmed against real Fusion geometry (2026-08-13): the offset
    direction (`faceDirChosen` below) ends up being the LONGER wall's own normal for Long
    Side, and the SHORTER wall's for Short Side - i.e. "which wall gets the bulge" is the
    wall NOT chosen as the offset direction, and Long Side bulges along the *shorter*
    wall while grazing/clearing the longer one (Short Side is the reverse). This is the
    opposite pairing from this function's first (hand-derived, untested) implementation -
    trust the code below, not the geometric intuition in this paragraph, if the two ever
    seem to disagree again. Falls back to the Corner-style formula for this one corner
    when either wall length is unmeasurable (wallLength1/wallLength2 is None - see
    measureAdjacentWallLength)."""
    if style == DogBoneStyle.CORNER:
        bisector = faceDir1.copy()
        bisector.add(faceDir2)
        bisector.normalize()
        bisector.scaleBy(max(0.0, radius - clearance))
        return bisector
    elif style == DogBoneStyle.MINIMAL_CORNER:
        bisector = faceDir1.copy()
        bisector.add(faceDir2)
        bisector.normalize()
        bisector.scaleBy(radius + interference)
        return bisector
    elif style in (DogBoneStyle.LONG_SIDE, DogBoneStyle.SHORT_SIDE):
        if wallLength1 is None or wallLength2 is None:
            bisector = faceDir1.copy()
            bisector.add(faceDir2)
            bisector.normalize()
            bisector.scaleBy(max(0.0, radius - clearance))
            return bisector
        wall1IsLonger = wallLength1 >= wallLength2
        wantBulgeOnLonger = (style == DogBoneStyle.LONG_SIDE)
        # Confirmed backwards against real Fusion geometry (2026-08-13) from the docstring's
        # hand-derived pairing above - swapped here to match what was actually observed.
        if wantBulgeOnLonger:
            faceDirChosen = faceDir1 if wall1IsLonger else faceDir2
        else:
            faceDirChosen = faceDir2 if wall1IsLonger else faceDir1
        offset = faceDirChosen.copy()
        offset.scaleBy(max(0.0, radius - clearance))
        return offset
    else:
        raise ValueError(f"Unknown dog bone style: {style}")


def buildDogBoneCylinder(edge, offset, radius):
    """Builds one relief cylinder spanning the candidate edge's own extent (its start/end
    vertices, unadjusted), shifted by `offset` from the true corner. On real topology the
    edge is already bounded exactly where its adjacent faces terminate, so - unlike the old
    bounding-box-based dog bone model - no separate "does this reach the panel's true face"
    computation is needed here."""
    pointOne = edge.startVertex.geometry.copy()
    pointOne.translateBy(offset)
    pointTwo = edge.endVertex.geometry.copy()
    pointTwo.translateBy(offset)
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    return temporaryBRepManager.createCylinderOrCone(pointOne, radius, pointTwo, radius)


def applyDogBonesToBody(candidates, style, radius, clearance, interference):
    """Unions every candidate corner's relief cylinder into one tool body. Returns a
    REMOVAL tool, not a pre-merged result - the caller cuts this from the target body, it
    must not be unioned with it. Returns None if there are no candidates.

    Long Side/Short Side's per-corner wall-length measurement derives its own axis from
    each candidate edge's own tangent direction, rather than taking one caller-supplied
    global plunge axis - a corner-relief cylinder's axis always runs along its own edge by
    construction, so this is exact for every candidate regardless of where it came from:
    Body/Face mode's auto-detection (which already constrains candidate edges to within
    ~1 degree of a real global plunge axis, so this is a no-op difference there) or Edge
    mode's direct user picks (which have no such guarantee - the user can select corners
    on differently-oriented faces of the same body, where no single global axis would be
    correct for all of them)."""
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    needsWallLengths = style in (DogBoneStyle.LONG_SIDE, DogBoneStyle.SHORT_SIDE)
    epsilon = 0.00001
    targetBody = None
    for edge, face1, face2 in candidates:
        n1 = getFaceOutwardNormal(face1)
        n2 = getFaceOutwardNormal(face2)
        wallLength1 = wallLength2 = None
        if needsWallLengths:
            edgeTangent = edge.startVertex.geometry.vectorTo(edge.endVertex.geometry)
            if edgeTangent.length > epsilon:
                edgeTangent.normalize()
                wallLength1 = measureAdjacentWallLength(edge, face1, edgeTangent)
                wallLength2 = measureAdjacentWallLength(edge, face2, edgeTangent)
        offset = computeDogBoneOffset(style, n1, n2, radius, clearance, interference, wallLength1, wallLength2)
        cylinder = buildDogBoneCylinder(edge, offset, radius)
        if cylinder is None:
            continue
        if targetBody is None:
            targetBody = cylinder
        else:
            temporaryBRepManager.booleanOperation(targetBody, cylinder, adsk.fusion.BooleanTypes.UnionBooleanType)
    return targetBody


def createToolBodies(inputs):
    overlap = createBodyFromOverlap(inputs.body0, inputs.body1)
    coordinateSystem = CoordinateSystem(inputs.direction, overlap)
    coordinateSystem.transformToLocalCoordinates(overlap)
    # TODO: look at MeasureManager.getOrientedBoundingBox to see if this can be simplified, probably with direction.geometry/worldGeometry

    bb = overlap.boundingBox
    height = bb.maxPoint.z - bb.minPoint.z
    if height <= 0:
        return True
    fingerDimensions, notchDimensions = defineToolBodyDimensions(height, inputs)
    if fingerDimensions is None or notchDimensions is None:
        return False

    if inputs.jointType == JointType.DOVETAIL:
        geom = _dovetailCombGeometry(overlap, inputs, coordinateSystem)
        fingerRawComb = _buildDovetailComb(fingerDimensions, geom)
        if fingerRawComb is None:
            return False
        # notchToolBody is built as fingerRawComb's exact geometric complement within a slab
        # spanning the full row, rather than an independently-derived tapered comb of its own -
        # see _buildDovetailComb's docstring for why deriving it independently (even with
        # mirrored/flipped wedge formulas) cannot produce walls that actually mate. Must happen
        # before fingerRawComb is finalized below (which intersects it with the real overlap
        # and scales it for gapToPart) - the complement needs the untouched raw comb so both
        # tools end up sharing identical boundary walls.
        tempBRep = adsk.fusion.TemporaryBRepManager.get()
        fullSlabBox = createBox(geom['cx'], geom['cy'], geom['minz'] + geom['size'] / 2,
                                 geom['length'], geom['width'], geom['size'])
        notchRawComb = tempBRep.createBox(fullSlabBox)
        tempBRep.booleanOperation(notchRawComb, fingerRawComb, adsk.fusion.BooleanTypes.DifferenceBooleanType)

        fingerToolBody = _finalizeDovetailToolBody(fingerRawComb, overlap, inputs, geom)
        notchToolBody = _finalizeDovetailToolBody(notchRawComb, overlap, inputs, geom)
    else:
        fingerToolBody = createToolBody(overlap, fingerDimensions, inputs)
        notchToolBody = createToolBody(overlap, notchDimensions, inputs)
    if fingerToolBody is None or notchToolBody is None:
        return False
    coordinateSystem.transformToGlobalCoordinates(fingerToolBody)
    coordinateSystem.transformToGlobalCoordinates(notchToolBody)
    return fingerToolBody, notchToolBody


def get_parametric_layout(inputs):
    """Calculates the 2D math and Coordinate System needed to build native timeline features."""
    overlap = createBodyFromOverlap(inputs.body0, inputs.body1)
    if not overlap: return None
    coordinateSystem = CoordinateSystem(inputs.direction, overlap)
    coordinateSystem.transformToLocalCoordinates(overlap)

    bb = overlap.boundingBox
    height = bb.maxPoint.z - bb.minPoint.z
    if height <= 0: return None

    fingerDimensions, notchDimensions = defineToolBodyDimensions(height, inputs)
    if fingerDimensions is None or notchDimensions is None: return None

    return {
        'cs': coordinateSystem,
        'finger_dims': fingerDimensions,
        'notch_dims': notchDimensions
    }

def defineToolBodyDimensions(size, inputs):
    placementType = inputs.placementType
    dynamicSizeType = inputs.dynamicSizeType
    minFingerSize = inputs.minFingerSize.value
    minNotchSize = inputs.minNotchSize.value
    fixedNotchSize = inputs.fixedNotchSize.value
    fixedFingerSize = inputs.fixedFingerSize.value
    isNumberOfFingersFixed = inputs.isNumberOfFingersFixed
    fixedNumFingers = inputs.fixedNumFingers
    gapSize = inputs.gap.value
    if isNumberOfFingersFixed:
        # The number of fingers is given, the number of notches depends on their placement.
        numFingers = fixedNumFingers
        if placementType == PlacementType.FINGERS_OUTSIDE:
            numNotches = numFingers - 1
        elif placementType == PlacementType.NOTCHES_OUTSIDE:
            numNotches = numFingers + 1
        else:
            numNotches = numFingers
        # Every finger and notch has a gap to its left except for the last one.
        numGaps = numFingers + numNotches - 1
        totalGapSize = numGaps * gapSize
        # Once the number of fingers and notches is fixed, their size can be determined.
        if dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE:
            fingerSize = (size - totalGapSize) / (numFingers + numNotches)
            notchSize = fingerSize
        elif dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE:
            notchSize = fixedNotchSize
            fingerSize = (size - totalGapSize - numNotches * notchSize) / numFingers
        elif dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE:
            fingerSize = fixedFingerSize
            notchSize = (size - totalGapSize - numFingers * fingerSize) / numNotches
    else: # Both fingers and notches are dynamically sized.

        # If fingers and notches have the same size, this size depends only on their placement and the minimal length.
        if dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE:
            # Across the size of the piece, we have to distribute F fingers, N notches and (F + N - 1) gaps.
            # The gaps have a fixed size g and we get size = (F + N) * w + (F + N - 1) * g. Solving for (F + N) gives
            # the formula to calculate the maximal number of fingers and notches we can place.
            maxNumFingersAndNotches = int((size + gapSize) / (minFingerSize + gapSize))
            # If there are the same number of fingers and notches the number needs to be even, otherwise odd.
            # We treat the number as even (rounding down) and correct when the number was odd.
            numFingers = numNotches = int(maxNumFingersAndNotches / 2)
            if placementType == PlacementType.FINGERS_OUTSIDE:
                if maxNumFingersAndNotches % 2 == 1:
                    numFingers += 1
                else:
                    numNotches -= 1
            elif placementType == PlacementType.NOTCHES_OUTSIDE:
                if maxNumFingersAndNotches % 2 == 1:
                    numNotches += 1
                else:
                    numFingers -= 1

            if numFingers + numNotches == 0:
                return None, None
            # Once the number of fingers and notches is known, we can compute their size.
            numGaps = numFingers + numNotches - 1
            totalGapSize = numGaps * gapSize
            fingerSize = (size - totalGapSize) / (numFingers + numNotches)
            notchSize = fingerSize

        # Notches have a fixed size, only fingers are dynamically sized.
        elif dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE:
            notchSize = fixedNotchSize
            # Depending on the placement, we either need an additional notch or an additional finger
            # (one less notch). 
            extraNotch = 0
            if placementType == PlacementType.FINGERS_OUTSIDE:
                extraNotch = -1
            elif placementType == PlacementType.NOTCHES_OUTSIDE:
                extraNotch = 1
            # Assuming we have F fingers of width f, N = F + x notches of width n, and G = (F + N - 1) gaps
            # of width g, the total size is size = F*f + (F+x)*n + (2F+x-1)*g.
            # Solving for F gives the number of fingers (rounding down because we used the minimal size for fingers).
            numFingers = int((size - extraNotch*(notchSize + gapSize) + gapSize) / (notchSize + minFingerSize + 2 * gapSize))
            numNotches = numFingers + extraNotch
            if numFingers == 0:
                return None, None
            numGaps = numFingers + numNotches - 1
            totalGapSize = numGaps * gapSize
            fingerSize = (size - totalGapSize - numNotches * notchSize) / numFingers

        # Fingers have a fixed size, only notches are dynamically sized.
        elif dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE:
            fingerSize = fixedFingerSize
            # Depending on the placement, we either need an additional finger or an additional notch
            # (one less finger).
            extraFinger = 0
            if placementType == PlacementType.FINGERS_OUTSIDE:
                extraFinger = 1
            elif placementType == PlacementType.NOTCHES_OUTSIDE:
                extraFinger = -1
            # Assuming we have N notches of width n, F = N + x fingers of width f, and G = (F + N - 1) gaps
            # of width g, the total size is size = (N+x)*f + N*n + (2N+x-1)*g.
            # Solving for N gives the number of notches (rounding down because we used the minimal size for notches).
            numNotches = int((size - extraFinger*(fingerSize + gapSize) + gapSize) / (fingerSize + minNotchSize + 2 * gapSize))
            numFingers = numNotches + extraFinger
            if numNotches == 0:
                return None, None
            numGaps = numFingers + numNotches - 1
            totalGapSize = numGaps * gapSize
            notchSize = (size - totalGapSize - numFingers * fingerSize) / numNotches

    # Sanity-check the dimensions before passing them along.
    epsilon = 0.00001 # avoid rounding issues with floats
    if (fingerSize <= epsilon
        or notchSize <= epsilon
        or numFingers < 0
        or numNotches < 0
        or numFingers + numNotches == 1
        or fingerSize * numFingers + notchSize * numNotches + (numFingers + numNotches - 1) * gapSize - epsilon > size):
        return None, None

    # Now that number and size of fingers and notches are defined, we set the position of the first finger.
    if placementType in [PlacementType.FINGERS_OUTSIDE, PlacementType.SAME_NUMBER_START_FINGER]:
        fingerStart = 0
        notchStart = fingerSize + gapSize
    else:
        fingerStart = notchSize + gapSize
        notchStart = 0

    # The tool bodies contain the full gap on both sides of the finger/notch.
    spacing = fingerSize + notchSize + 2 * gapSize

    # The tool for cutting fingers consists of all places where there are notches or gaps (everything other than a finger).
    fingerToolDimensions = [(notchStart + i*spacing - gapSize, notchSize + 2 * gapSize) for i in range(numNotches)]
    # The tool for cutting notches consists of all places where there are fingers or gaps (everything other than a notch).
    notchToolDimensions = [(fingerStart + i*spacing - gapSize, fingerSize + 2 * gapSize) for i in range(numFingers)]

    # A negative gapSize (press-fit kerf compensation) shrinks each tool interval instead of
    # growing it, which can pull an outermost interval's edge back past the true ends of the
    # row (0 and size), leaving an uncut sliver of material at the row's true boundary - visible
    # as a proud tab at open ends and at box corners alike.
    #
    # At a given end of the row, only ONE of the two tools needs to reach the true bound: the
    # one that clears the boundary feature's footprint on the *mating* body (e.g. if a finger
    # sits at the row's start, the notch tool must cut flush to x=0 there). The other tool's
    # outermost interval legitimately starts partway into the row - at exactly that boundary
    # feature's own size - and must NOT be extended, or it would cut the boundary feature away
    # entirely. So we first determine which feature type occupies each end, then extend only
    # the complementary tool. This is a no-op for positive gapSize, which already overshoots
    # past the bound harmlessly.
    def extendStartIfNeeded(dimensions):
        if not dimensions:
            return
        start, length = dimensions[0]
        if start > 0:
            dimensions[0] = (0, length + start)

    def extendEndIfNeeded(dimensions):
        if not dimensions:
            return
        start, length = dimensions[-1]
        end = start + length
        if end < size:
            dimensions[-1] = (start, size - start)

    if fingerStart == 0:
        extendStartIfNeeded(notchToolDimensions)
    else:
        extendStartIfNeeded(fingerToolDimensions)

    lastFingerEnd = fingerStart + (numFingers - 1) * spacing + fingerSize
    lastNotchEnd = notchStart + (numNotches - 1) * spacing + notchSize
    if lastFingerEnd > lastNotchEnd:
        extendEndIfNeeded(notchToolDimensions)
    else:
        extendEndIfNeeded(fingerToolDimensions)

    return fingerToolDimensions, notchToolDimensions
