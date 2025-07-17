import cv2
import numpy as np

def resize(image, width=None, height=None, inter=cv2.INTER_AREA):
    """Resize image while maintaining aspect ratio"""
    dim = None
    (h, w) = image.shape[:2]
    
    if width is None and height is None:
        return image
    
    if width is None:
        r = height / float(h)
        dim = (int(w * r), height)
    else:
        r = width / float(w)
        dim = (width, int(h * r))
    
    resized = cv2.resize(image, dim, interpolation=inter)
    return resized

def transform(image):
    """Transform image for better plate detection"""
    # Convert to grayscale if needed
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Apply edge detection
    edges = cv2.Canny(blurred, 50, 150)
    
    # Convert back to BGR for consistency
    if len(image.shape) == 3:
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    else:
        return edges

def rotate(image, angle, center=None, scale=1.0):
    """Rotate image around center point"""
    (h, w) = image.shape[:2]
    
    if center is None:
        center = (w / 2, h / 2)
    
    M = cv2.getRotationMatrix2D(center, angle, scale)
    rotated = cv2.warpAffine(image, M, (w, h))
    
    return rotated