import adsk.core
import adsk.fusion

from .options import DynamicSizeType, PlacementType


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
    def __init__(self, direction):
        if isinstance(direction, adsk.fusion.BRepEdge):
            self.origin = direction.startVertex.geometry
            self.direction = self.origin.vectorTo(direction.endVertex.geometry)
        else:
            assert(isinstance(direction, adsk.fusion.SketchLine))
            self.origin = direction.startSketchPoint.worldGeometry
            self.direction = self.origin.vectorTo(direction.endSketchPoint.worldGeometry)
        self.direction.normalize()

        xAxis, yAxis = findOrthogonalUnitVectors(self.direction)
        self.transform = adsk.core.Matrix3D.create()
        self.transform.setWithCoordinateSystem(
            self.origin,
            xAxis,
            yAxis, 
            self.direction)

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


def createToolBody(body, slices, debug=False):
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
    return targetBody


def createBodyFromOverlap(body0, body1):
    temporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    overlapBody = temporaryBRepManager.copy(body0)
    temporaryBRepManager.booleanOperation(overlapBody, body1, adsk.fusion.BooleanTypes.IntersectionBooleanType)
    return overlapBody


def createToolBodies(body0, body1, direction, options):
    coordinateSystem = CoordinateSystem(direction)
    overlap = createBodyFromOverlap(body0, body1)
    coordinateSystem.transformToLocalCoordinates(overlap)
    # TODO: look at MeasureManager.getOrientedBoundingBox to see if this can be simplified, probably with direction.geometry/worldGeometry

    bb = overlap.boundingBox
    height = bb.maxPoint.z - bb.minPoint.z
    if height <= 0:
        return True
    fingerDimensions, notchDimensions = defineToolBodyDimensions(height, options)
    if fingerDimensions is None or notchDimensions is None:
        return False

    fingerToolBody = createToolBody(overlap, fingerDimensions)
    coordinateSystem.transformToGlobalCoordinates(fingerToolBody)
    notchToolBody = createToolBody(overlap, notchDimensions)
    coordinateSystem.transformToGlobalCoordinates(notchToolBody)
    return fingerToolBody, notchToolBody


def defineToolBodyDimensions(size, options):
    gapSize = options.gap
    if options.isNumberOfFingersFixed:
        # The number of fingers is given, the number of notches depends on their placement.
        numFingers = options.fixedNumFingers
        if options.placementType == PlacementType.FINGERS_OUTSIDE:
            numNotches = numFingers - 1
        elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
            numNotches = numFingers + 1
        else:
            numNotches = numFingers
        # Every finger and notch has a gap to its left except for the last one.
        numGaps = numFingers + numNotches - 1
        totalGapSize = numGaps * gapSize
        # Once the number of fingers and notches is fixed, their size can be determined.
        if options.dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE:
            fingerSize = (size - totalGapSize) / (numFingers + numNotches)
            notchSize = fingerSize
        elif options.dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE:
            notchSize = options.fixedNotchSize
            fingerSize = (size - totalGapSize - numNotches * notchSize) / numFingers
        elif options.dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE:
            fingerSize = options.fixedFingerSize
            notchSize = (size - totalGapSize - numFingers * fingerSize) / numNotches
    else: # Both fingers and notches are dynamically sized.

        # If fingers and notches have the same size, this size depends only on their placement and the minimal length.
        if options.dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE:
            # Across the size of the piece, we have to distribute F fingers, N notches and (F + N - 1) gaps.
            # The gaps have a fixed size g and we get size = (F + N) * w + (F + N - 1) * g. Solving for (F + N) gives
            # the formula to calculate the maximal number of fingers and notches we can place.
            maxNumFingersAndNotches = int((size + gapSize) / (options.minFingerSize + gapSize))
            # If there are the same number of fingers and notches the number needs to be even, otherwise odd.
            # We treat the number as even (rounding down) and correct when the number was odd.
            numFingers = numNotches = int(maxNumFingersAndNotches / 2)
            if options.placementType == PlacementType.FINGERS_OUTSIDE:
                if maxNumFingersAndNotches % 2 == 1:
                    numFingers += 1
                else:
                    numNotches -= 1
            elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
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
        elif options.dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE:
            notchSize = options.fixedNotchSize
            # Depending on the placement, we either need an additional notch or an additional finger
            # (one less notch). 
            extraNotch = 0
            if options.placementType == PlacementType.FINGERS_OUTSIDE:
                extraNotch = -1
            elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
                extraNotch = 1
            # Assuming we have F fingers of width f, N = F + x notches of width n, and G = (F + N - 1) gaps
            # of width g, the total size is size = F*f + (F+x)*n + (2F+x-1)*g.
            # Solving for F gives the number of fingers (rounding down because we used the minimal size for fingers).
            numFingers = int((size - extraNotch*(notchSize + gapSize) + gapSize) / (notchSize + options.minFingerSize + 2 * gapSize))
            numNotches = numFingers + extraNotch
            if numFingers == 0:
                return None, None
            numGaps = numFingers + numNotches - 1
            totalGapSize = numGaps * gapSize
            fingerSize = (size - totalGapSize - numNotches * notchSize) / numFingers

        # Fingers have a fixed size, only notches are dynamically sized.
        elif options.dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE:
            fingerSize = options.fixedFingerSize
            # Depending on the placement, we either need an additional finger or an additional notch
            # (one less finger).
            extraFinger = 0
            if options.placementType == PlacementType.FINGERS_OUTSIDE:
                extraFinger = 1
            elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
                extraFinger = -1
            # Assuming we have N notches of width n, F = N + x fingers of width f, and G = (F + N - 1) gaps
            # of width g, the total size is size = (N+x)*f + N*n + (2N+x-1)*g.
            # Solving for N gives the number of notches (rounding down because we used the minimal size for notches).
            numNotches = int((size - extraFinger*(fingerSize + gapSize) + gapSize) / (fingerSize + options.minNotchSize + 2 * gapSize))
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
    if options.placementType in [PlacementType.FINGERS_OUTSIDE, PlacementType.SAME_NUMBER_START_FINGER]:
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
    return fingerToolDimensions, notchToolDimensions
