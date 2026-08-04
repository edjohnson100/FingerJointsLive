import math

import adsk.core
import adsk.fusion

from .options import DynamicSizeType, JointType, PlacementType


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


def _dovetailCombGeometry(body, inputs):
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

    depthIsX = (maxx - minx) <= (maxy - miny)
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
        geom = _dovetailCombGeometry(overlap, inputs)
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
