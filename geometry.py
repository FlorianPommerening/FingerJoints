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


def createSlicesBody(body, slices, debug=False):
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

def cutFingersIntoBodies(body0, body1, fingers):
    app = adsk.core.Application.get()
    root = app.activeProduct.rootComponent
    combineFeatures = root.features.combineFeatures

    # Add the fingers to the document so they can interact with the other bodies in the document.
    feature = root.features.baseFeatures.add()
    feature.startEdit()
    root.bRepBodies.add(fingers, feature)
    feature.finishEdit()
    
    # Cut the fingers out of body1.
    fingerCollection = adsk.core.ObjectCollection.create()
    for i in range(feature.bodies.count):
        fingerCollection.add(feature.bodies.item(i))
    cut1Input = combineFeatures.createInput(body1, fingerCollection)
    cut1Input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    combineFeature = combineFeatures.add(cut1Input)

    # Cut body0 with body1 (since we removed the fingers from body1, this leaves them on body0).
    body1Collection = adsk.core.ObjectCollection.create()
    for i in range(combineFeature.bodies.count):
        body1Collection.add(combineFeature.bodies.item(i))
    cut0Input = combineFeatures.createInput(body0, body1Collection)
    cut0Input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
    cut0Input.isKeepToolBodies = True
    combineFeatures.add(cut0Input)


def createFingerJoint(body0, body1, direction, options):
    coordinateSystem = CoordinateSystem(direction)
    overlap = createBodyFromOverlap(body0, body1)
    coordinateSystem.transformToLocalCoordinates(overlap)
    # TODO: look at MeasureManager.getOrientedBoundingBox to see if this can be simplified, probably with direction.geometry/worldGeometry

    bb = overlap.boundingBox
    height = bb.maxPoint.z - bb.minPoint.z
    if height <= 0:
        return True
    slices = defineSlices(height, options)
    if slices is None:
        return False

    fingers = createSlicesBody(overlap, slices)
    coordinateSystem.transformToGlobalCoordinates(fingers)
    cutFingersIntoBodies(body0, body1, fingers)
    return True


def defineSlices(size, options):
    if options.isNumberOfFingersFixed:
        # The number of fingers is given, the number of notches depends on their placement.
        numFingers = options.fixedNumFingers
        if options.placementType == PlacementType.FINGERS_OUTSIDE:
            numNotches = numFingers - 1
        elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
            numNotches = numFingers + 1
        else:
            numNotches = numFingers
        # Once the number of fingers and notches is fixed, their size can be determined.
        if options.dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE:
            fingerSize = size / (numFingers + numNotches)
            notchSize = fingerSize
        elif options.dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE:
            notchSize = options.fixedNotchSize
            fingerSize = (size - numNotches * notchSize) / numFingers
        elif options.dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE:
            fingerSize = options.fixedFingerSize
            notchSize = (size - numFingers * fingerSize) / numNotches
    else: # Both fingers and notches are dynamically sized.

        # If fingers and notches have the same size, this size depends only on their placement and the minimal length.
        if options.dynamicSizeType == DynamicSizeType.EQUAL_NOTCH_AND_FINGER_SIZE:
            maxNumFingersAndNotches = int(size / options.minFingerSize)
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
                return None
            # Once the number of fingers and notches is known, we can compute their size.
            fingerSize = size / (numFingers + numNotches)
            notchSize = fingerSize

        # Notches have a fixed size, only fingers are dynamically sized.
        elif options.dynamicSizeType == DynamicSizeType.FIXED_NOTCH_SIZE:
            notchSize = options.fixedNotchSize
            # Depending on the placement, we either need an additional notch or an additional finger
            # (one less notch). We pretend the part is longer or shorter by the size of one notch in
            # this case. This way, the virtual part always contains the same number of fingers as notches.
            extraNotch = 0
            if options.placementType == PlacementType.FINGERS_OUTSIDE:
                extraNotch = -1
            elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
                extraNotch = 1
            virtualSize = size - extraNotch * notchSize
            numFingers = int(virtualSize / (notchSize + options.minFingerSize))
            numNotches = numFingers + extraNotch
            if numFingers == 0:
                return None
            fingerSize = (size - numNotches * notchSize) / numFingers

        # Fingers have a fixed size, only notches are dynamically sized.
        elif options.dynamicSizeType == DynamicSizeType.FIXED_FINGER_SIZE:
            fingerSize = options.fixedFingerSize
            # Depending on the placement, we either need an additional finger or an additional notch
            # (one less finger). We pretend the part is longer or shorter by the size of one finger in
            # this case. This way, the virtual part always contains the same number of fingers as notches.
            extraFinger = 0
            if options.placementType == PlacementType.FINGERS_OUTSIDE:
                extraFinger = 1
            elif options.placementType == PlacementType.NOTCHES_OUTSIDE:
                extraFinger = -1
            virtualSize = size - extraFinger * fingerSize
            numNotches = int(virtualSize / (fingerSize + options.minNotchSize))
            numFingers = numNotches + extraFinger
            if numNotches == 0:
                return None
            notchSize = (size - numFingers * fingerSize) / numNotches

    # Now that number and size of fingers and notches are defined, we set the position of the first finger.
    if options.placementType in [PlacementType.FINGERS_OUTSIDE, PlacementType.SAME_NUMBER_START_FINGER]:
        fingerStart = 0
    else:
        fingerStart = notchSize

    # Sanity-check the dimensions before passing them along.
    epsilon = 0.00001 # avoid rounding issues with floats
    if (fingerSize <= epsilon
        or notchSize <= epsilon
        or numFingers < 0
        or numNotches < 0
        or numFingers + numNotches == 1
        or fingerSize * numFingers + notchSize * numNotches - epsilon > size):
        return None

    fingerDistance = fingerSize + notchSize
    return [(fingerStart + i*fingerDistance, fingerSize) for i in range(numFingers)]
