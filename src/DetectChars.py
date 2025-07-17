import cv2
import numpy as np
import os
import operator
import math

# Constants for character detection
MIN_PIXEL_WIDTH = 2
MIN_PIXEL_HEIGHT = 8

MIN_ASPECT_RATIO = 0.25
MAX_ASPECT_RATIO = 1.0

MIN_PIXEL_AREA = 80

MIN_DIAG_SIZE_MULTIPLE_AWAY = 0.3
MAX_DIAG_SIZE_MULTIPLE_AWAY = 5.0

MAX_CHANGE_IN_AREA = 0.5
MAX_CHANGE_IN_WIDTH = 0.8
MAX_CHANGE_IN_HEIGHT = 0.2

MAX_ANGLE_BETWEEN_CHARS = 12.0

MIN_NUMBER_OF_MATCHING_CHARS = 3

RESIZED_CHAR_IMAGE_WIDTH = 20
RESIZED_CHAR_IMAGE_HEIGHT = 30

MIN_CONTOUR_AREA = 100

# Global variables
kNearest = cv2.ml.KNearest_create()

class ContourWithData:
    """Container for contour data"""
    npaContour = None
    boundingRect = None
    intRectX = 0
    intRectY = 0
    intRectWidth = 0
    intRectHeight = 0
    fltArea = 0.0
    
    def calculateRectTopLeftPointAndWidthAndHeight(self):
        [intX, intY, intWidth, intHeight] = self.boundingRect
        self.intRectX = intX
        self.intRectY = intY
        self.intRectWidth = intWidth
        self.intRectHeight = intHeight
    
    def checkIfContourIsValid(self):
        if self.fltArea < MIN_CONTOUR_AREA:
            return False
        return True

def loadKNNDataAndTrainKNN():
    """Load KNN training data and train the model"""
    try:
        # Try to load training data
        npaClassifications = np.loadtxt("data/training_data/classifications.txt", np.float32)
        npaFlattenedImages = np.loadtxt("data/training_data/flattened_images.txt", np.float32)
        
        npaClassifications = npaClassifications.reshape((npaClassifications.size, 1))
        
        kNearest.setDefaultK(1)
        kNearest.train(npaFlattenedImages, cv2.ml.ROW_SAMPLE, npaClassifications)
        
        return True
    except:
        print("Error: unable to open KNN training data")
        return False

def detectCharsInPlates(listOfPossiblePlates):
    """Detect characters in license plates"""
    intPlateCounter = 0
    imgContours = None
    contours = []
    
    if len(listOfPossiblePlates) == 0:
        return listOfPossiblePlates
    
    for possiblePlate in listOfPossiblePlates:
        possiblePlate.imgGrayscale, possiblePlate.imgThresh = preprocess(possiblePlate.imgPlate)
        
        if possiblePlate.imgGrayscale is None or possiblePlate.imgThresh is None:
            continue
        
        # Find contours in plate
        imgThreshCopy = possiblePlate.imgThresh.copy()
        
        contours, npaHierarchy = cv2.findContours(imgThreshCopy, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        height, width = possiblePlate.imgThresh.shape
        imgContours = np.zeros((height, width, 3), np.uint8)
        
        del contours[:]
        
        for npaContour in contours:
            contourWithData = ContourWithData()
            contourWithData.npaContour = npaContour
            contourWithData.boundingRect = cv2.boundingRect(npaContour)
            contourWithData.calculateRectTopLeftPointAndWidthAndHeight()
            contourWithData.fltArea = cv2.contourArea(npaContour)
            
            if contourWithData.checkIfContourIsValid():
                contours.append(contourWithData)
        
        listOfListsOfMatchingCharsInPlate = findListOfListsOfMatchingChars(contours)
        
        if len(listOfListsOfMatchingCharsInPlate) == 0:
            continue
        
        for i in range(0, len(listOfListsOfMatchingCharsInPlate)):
            listOfListsOfMatchingCharsInPlate[i].sort(key=lambda matchingChar: matchingChar.intRectX)
            listOfListsOfMatchingCharsInPlate[i] = removeInnerOverlappingChars(listOfListsOfMatchingCharsInPlate[i])
        
        intLenOfLongestListOfChars = 0
        intIndexOfLongestListOfChars = 0
        
        for i in range(0, len(listOfListsOfMatchingCharsInPlate)):
            if len(listOfListsOfMatchingCharsInPlate[i]) > intLenOfLongestListOfChars:
                intLenOfLongestListOfChars = len(listOfListsOfMatchingCharsInPlate[i])
                intIndexOfLongestListOfChars = i
        
        longestListOfMatchingCharsInPlate = listOfListsOfMatchingCharsInPlate[intIndexOfLongestListOfChars]
        
        possiblePlate.strChars = recognizeCharsInPlate(possiblePlate.imgThresh, longestListOfMatchingCharsInPlate)
        
        intPlateCounter += 1
    
    return listOfPossiblePlates

def findListOfListsOfMatchingChars(listOfContours):
    """Find groups of matching characters"""
    listOfListsOfMatchingChars = []
    
    for contour in listOfContours:
        listOfMatchingChars = findListOfMatchingChars(contour, listOfContours)
        listOfMatchingChars.append(contour)
        
        if len(listOfMatchingChars) < MIN_NUMBER_OF_MATCHING_CHARS:
            continue
        
        listOfListsOfMatchingChars.append(listOfMatchingChars)
        
        listOfContoursWithMatchingChars = []
        listOfContoursWithMatchingChars.append(contour)
        
        for matchingChar in listOfMatchingChars:
            listOfContoursWithMatchingChars.append(matchingChar)
        
        listOfContoursWithoutMatchingChars = []
        
        for contour in listOfContours:
            if contour not in listOfContoursWithMatchingChars:
                listOfContoursWithoutMatchingChars.append(contour)
        
        recursiveListOfListsOfMatchingChars = findListOfListsOfMatchingChars(listOfContoursWithoutMatchingChars)
        
        for recursiveListOfMatchingChars in recursiveListOfListsOfMatchingChars:
            listOfListsOfMatchingChars.append(recursiveListOfMatchingChars)
        
        break
    
    return listOfListsOfMatchingChars

def findListOfMatchingChars(possibleChar, listOfChars):
    """Find characters that match with the given character"""
    listOfMatchingChars = []
    
    for possibleMatchingChar in listOfChars:
        if possibleMatchingChar == possibleChar:
            continue
        
        fltDistanceBetweenChars = distanceBetweenChars(possibleChar, possibleMatchingChar)
        fltAngleBetweenChars = angleBetweenChars(possibleChar, possibleMatchingChar)
        
        fltChangeInArea = float(abs(possibleMatchingChar.fltArea - possibleChar.fltArea)) / float(possibleChar.fltArea)
        fltChangeInWidth = float(abs(possibleMatchingChar.intRectWidth - possibleChar.intRectWidth)) / float(possibleChar.intRectWidth)
        fltChangeInHeight = float(abs(possibleMatchingChar.intRectHeight - possibleChar.intRectHeight)) / float(possibleChar.intRectHeight)
        
        if (fltDistanceBetweenChars < (possibleChar.fltArea * MAX_DIAG_SIZE_MULTIPLE_AWAY) and
            fltAngleBetweenChars < MAX_ANGLE_BETWEEN_CHARS and
            fltChangeInArea < MAX_CHANGE_IN_AREA and
            fltChangeInWidth < MAX_CHANGE_IN_WIDTH and
            fltChangeInHeight < MAX_CHANGE_IN_HEIGHT):
            
            listOfMatchingChars.append(possibleMatchingChar)
    
    return listOfMatchingChars

def distanceBetweenChars(firstChar, secondChar):
    """Calculate distance between two characters"""
    intX = abs(firstChar.intRectX - secondChar.intRectX)
    intY = abs(firstChar.intRectY - secondChar.intRectY)
    
    return math.sqrt((intX ** 2) + (intY ** 2))

def angleBetweenChars(firstChar, secondChar):
    """Calculate angle between two characters"""
    fltAdj = float(abs(firstChar.intRectX - secondChar.intRectX))
    fltOpp = float(abs(firstChar.intRectY - secondChar.intRectY))
    
    if fltAdj != 0.0:
        fltAngleInRad = math.atan(fltOpp / fltAdj)
    else:
        fltAngleInRad = 1.5708
    
    fltAngleInDeg = fltAngleInRad * (180.0 / math.pi)
    
    return fltAngleInDeg

def removeInnerOverlappingChars(listOfMatchingChars):
    """Remove overlapping characters"""
    listOfMatchingCharsWithInnerCharsRemoved = []
    
    for currentChar in listOfMatchingChars:
        blnIsInnerChar = False
        
        for otherChar in listOfMatchingChars:
            if currentChar == otherChar:
                continue
            
            if (currentChar.intRectX > otherChar.intRectX and
                currentChar.intRectY > otherChar.intRectY and
                currentChar.intRectX + currentChar.intRectWidth < otherChar.intRectX + otherChar.intRectWidth and
                currentChar.intRectY + currentChar.intRectHeight < otherChar.intRectY + otherChar.intRectHeight):
                blnIsInnerChar = True
                break
        
        if not blnIsInnerChar:
            listOfMatchingCharsWithInnerCharsRemoved.append(currentChar)
    
    return listOfMatchingCharsWithInnerCharsRemoved

def recognizeCharsInPlate(imgThresh, listOfMatchingChars):
    """Recognize characters in a plate"""
    strChars = ""
    
    height, width = imgThresh.shape
    
    imgThreshColor = np.zeros((height, width, 3), np.uint8)
    
    listOfMatchingChars.sort(key=lambda matchingChar: matchingChar.intRectX)
    
    cv2.cvtColor(imgThresh, cv2.COLOR_GRAY2BGR, imgThreshColor)
    
    for currentChar in listOfMatchingChars:
        pt1 = (currentChar.intRectX, currentChar.intRectY)
        pt2 = ((currentChar.intRectX + currentChar.intRectWidth), (currentChar.intRectY + currentChar.intRectHeight))
        
        cv2.rectangle(imgThreshColor, pt1, pt2, (0, 255, 0), 2)
        
        imgROI = imgThresh[currentChar.intRectY : currentChar.intRectY + currentChar.intRectHeight,
                         currentChar.intRectX : currentChar.intRectX + currentChar.intRectWidth]
        
        imgROIResized = cv2.resize(imgROI, (RESIZED_CHAR_IMAGE_WIDTH, RESIZED_CHAR_IMAGE_HEIGHT))
        
        npaROIResized = imgROIResized.reshape((1, RESIZED_CHAR_IMAGE_WIDTH * RESIZED_CHAR_IMAGE_HEIGHT))
        
        npaROIResized = np.float32(npaROIResized)
        
        retval, npaResults, neigh_resp, dists = kNearest.findNearest(npaROIResized, k=1)
        
        strCurrentChar = str(chr(int(npaResults[0][0])))
        
        strChars = strChars + strCurrentChar
    
    return strChars

def preprocess(imgOriginal):
    """Preprocess image for character detection"""
    imgGrayscale = cv2.cvtColor(imgOriginal, cv2.COLOR_BGR2GRAY)
    
    imgMaxContrastGrayscale = maximizeContrast(imgGrayscale)
    
    height, width = imgGrayscale.shape
    imgBlurred = np.zeros((height, width, 1), np.uint8)
    
    imgBlurred = cv2.GaussianBlur(imgMaxContrastGrayscale, (5, 5), 0)
    
    imgThresh = cv2.adaptiveThreshold(imgBlurred, 255.0, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 19, 9)
    
    return imgGrayscale, imgThresh

def maximizeContrast(imgGrayscale):
    """Maximize contrast of grayscale image"""
    height, width = imgGrayscale.shape
    
    imgTopHat = np.zeros((height, width, 1), np.uint8)
    imgBlackHat = np.zeros((height, width, 1), np.uint8)
    
    structuringElement = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    
    imgTopHat = cv2.morphologyEx(imgGrayscale, cv2.MORPH_TOPHAT, structuringElement)
    imgBlackHat = cv2.morphologyEx(imgGrayscale, cv2.MORPH_BLACKHAT, structuringElement)
    
    imgGrayscalePlusTopHat = cv2.add(imgGrayscale, imgTopHat)
    imgGrayscalePlusTopHatMinusBlackHat = cv2.subtract(imgGrayscalePlusTopHat, imgBlackHat)
    
    return imgGrayscalePlusTopHatMinusBlackHat
