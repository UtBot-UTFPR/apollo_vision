#!/usr/bin/env python3

import rospy
from sensor_msgs.msg import Image, RegionOfInterest
from vision_msgs.msg import Object, ObjectArray
from geometry_msgs.msg import PointStamped, Point, TransformStamped
from tf.msg import tfMessage
from cv_bridge import CvBridge  
import cv2
# Math 
import numpy as np
from math import pow, sqrt, sin, tan, radians

class Extract3DCentroid():
    def __init__(self, topicDepthImg, topicObject, camFov_vertical, camFov_horizontal):
        # Image FOV for trig calculations
        self.camFov_vertical = camFov_vertical
        self.camFov_horizontal = camFov_horizontal

        # Messages
        self.msg_tfStamped          = TransformStamped()
        self.msg_cvDepthImg         = None
        self.msg_roi                = RegionOfInterest()
        self.msg_obj                = Object()
        self.msg_centroidPoint      = PointStamped()
        self.msg_centroidPoint.header.frame_id = "object_center"
        self.msg_cropped = Image()

        # Flags
        self.new_depthMsg = False
        self.new_objMsg = False

        # Subscribers
        self.sub_depthImg = rospy.Subscriber(topicDepthImg, Image, self.callback_depthImg)
        self.sub_object = rospy.Subscriber(topicObject, Object, self.callback_object)
        
        self.pub_centroidPoint = rospy.Publisher(
            "/utbots/vision/selected/objectPoint", PointStamped, queue_size=1)
        self.pub_cropped = rospy.Publisher(
            "/utbots/vision/selected/croppedImg", Image, queue_size=1)
        self.pub_tf = rospy.Publisher(
            "/tf", tfMessage, queue_size=10)
        
        # Cv
        self.cvBridge = CvBridge()
        
        rospy.init_node("extract_3d_centroid", anonymous=True)

        # Time
        self.loopRate = rospy.Rate(50)
        self.mainLoop()

    def callback_depthImg(self, msg):
        self.msg_cvDepthImg = self.cvBridge.imgmsg_to_cv2(msg, "32FC1")
        x0 = self.msg_obj.roi.x_offset
        y0 = self.msg_obj.roi.y_offset
        xf = x0 + (self.msg_obj.roi.width)
        yf = y0 + (self.msg_obj.roi.height)
        # print(str(x0) + " " + str(xf) + " " + str(y0) + " " + str(xf))
        self.msg_cvDepthImg = self.msg_cvDepthImg[y0:yf, x0:xf]
        self.msg_cropped = self.cvBridge.cv2_to_imgmsg(self.msg_cvDepthImg, "passthrough")
        self.new_depthMsg = True

    def callback_object(self, msg):
        self.msg_obj = msg
        # print(str(self.msg_obj.roi.x_offset) + " " + str(self.msg_obj.roi.y_offset) + " " + str(self.msg_obj.roi.width) + " " + str(self.msg_obj.roi.height))
        self.new_objMsg = True

    def movingAverage(self, new_value, current_mean, n_values):
        return current_mean+(new_value-current_mean)/n_values
    
    def quarterFrameAverage(self, subframe, ver_start, ver_stop, ver_step, hor_start, hor_stop, hor_step):
        # Iterates through the image from the start to the stop indexes, using the step defined
        for i in range(ver_start, ver_stop, ver_step):
            for j in range(hor_start, hor_stop, hor_step):
                # print("["+str(i)+","+str(j)+"]:" + str(subframe[i][j]))
                # First point evaluated
                if i == ver_start and j == hor_start:
                    subframe_mean = subframe[i][j]
                    n_values = 1
                # If the pixel value diference to the mean is less than 100mm (10cm), adds to the mean
                elif subframe[i][j] - subframe_mean < 100:
                    # print(subframe[i][j] - subframe_mean)
                    n_values += 1
                    subframe_mean = self.movingAverage(subframe[i][j], subframe_mean, n_values)
        return subframe_mean

    def getMeanDistance4(self):
        # Frame dimensions
        height = self.msg_obj.roi.height
        width = self.msg_obj.roi.width

        # Stores the point distances of every point inside the object's region of interest

        # Divide the total frame into 4 subframes
        btm_left =  self.msg_cvDepthImg[0:(height//2)        , 0:(width//2)      ]
        top_left =  self.msg_cvDepthImg[(height//2+1):height , 0:(width//2)      ]
        btm_right = self.msg_cvDepthImg[0:(height//2)        , (width//2+1):width]
        top_right = self.msg_cvDepthImg[(height//2+1):height , (width//2+1):width]

        # Calculates the average of all 4 subframes
        btm_left_mean =  self.quarterFrameAverage(btm_left, len(btm_left)-1, -1, -1, len(btm_left[0])-1, -1, -1,)
        top_left_mean =  self.quarterFrameAverage(top_left, 0, len(top_left), 1, len(btm_left[0])-1, -1, -1)
        btm_right_mean = self.quarterFrameAverage(btm_right, len(btm_right)-1, -1, -1, 0, len(btm_right[0]), 1)
        top_right_mean = self.quarterFrameAverage(top_right, 0, len(top_right), 1, 0, len(top_right[0]), 1)

        return (btm_left_mean + top_left_mean + btm_right_mean + top_right_mean)/4

    def getMeanDistance(self):
        height, width = self.msg_cvDepthImg.shape
        npArray = self.msg_cvDepthImg[0:height, 0:width]

        rowMeans = np.array([])
        for row in npArray:
            rowMeans = np.append(rowMeans, np.mean(row))

        depthMean = np.mean(rowMeans)
        return depthMean

    def getMeanDistanceWoutOutliers(self):
        allpixels = np.array([])
        height, width = self.msg_cvDepthImg.shape
        image = self.msg_cvDepthImg[0:height, 0:width]

        if image.size > 0:
            # Add every pixel to a list
            for i in range(0, height):
                for j in range(0, width):
                    if(image[i][j] != 0):
                        print(image[i][j])
                        allpixels = np.append(allpixels, image[i][j])

            # Sorted list
            allpixels = np.sort(allpixels)

            q3 = np.percentile(allpixels, 75)
            q1 = np.percentile(allpixels, 25)
            interquartile = q3 - q1
            max = q3 + (1.5*interquartile)
            min = q1 - (1.5*interquartile)

            filteredpixels = np.array([])

            # Add only pixels within the min and max boundary to a np.array (filtered outliers)
            for pixel in allpixels:
                if(pixel < max and pixel > min):
                    filteredpixels = np.append(filteredpixels, pixel)

            # Returns the mean
            print(image.size)
            return np.mean(filteredpixels)
        else:
            return 0

    # Redefines the xy point scale from 0-height and 0-width to a percentage of the total size scale in both dimensions (0-1)
    def redefineScale(self, point):
        x = point.x/self.msg_obj.parent_img.width
        y = point.y/self.msg_obj.parent_img.height
        return Point(x, y, 0)

    def calculate_3d_centroid(self, roi):
        mean_y = roi.y_offset + roi.height//2
        mean_x = roi.x_offset + roi.width//2
        return self.get3dPointFromDepthPixel(self.redefineScale(Point(mean_x, mean_y, 0)), self.getMeanDistanceWoutOutliers())
    
    # By using rule of three and considering the FOV of the camera: Calculates the 3D point of a depth pixel '''
    def get3dPointFromDepthPixel(self, pixel, distance):
        width  = 1.0
        height = 1.0

        # Centralize the camera reference at (0,0,0)
        ## (x,y,z) are respectively horizontal, vertical and depth
        ## Theta is the angle of the point with z axis in the zx plane
        ## Phi is the angle of the point with z axis in the zy plane
        ## x_max is the distance of the side border from the camera
        ## y_max is the distance of the upper border from the camera
        theta_max = self.camFov_horizontal/2 
        phi_max = self.camFov_vertical/2
        x_max = width/2.0
        y_max = height/2.0
        x = pixel.x - x_max
        y = pixel.y - y_max

        # Caculate point theta and phi
        theta = radians(theta_max * x / x_max)
        phi = radians(phi_max * y / y_max)

        # Convert the spherical radius rho from Kinect's mm to meter
        rho = distance/1000

        # Calculate x, y and z
        y = rho * sin(phi)
        x = sqrt(pow(rho, 2) - pow(y, 2)) * sin(theta)
        z = x / tan(theta)

        # Change coordinate scheme
        ## We calculate with (x,y,z) respectively horizontal, vertical and depth
        ## For the plot in 3d space, we need to remap the coordinates to (z, -x, -y)
        point_zxy = Point(z, -x, -y)

        print(str(z))

        return point_zxy

    
    # Transformation tree methods
    def SetupTfMsg(self):
        self.msg_tfStamped.header.frame_id = "camera_link"
        self.msg_tfStamped.header.stamp = rospy.Time.now()
        self.msg_tfStamped.child_frame_id = "object_center"
        self.msg_tfStamped.transform.translation.x = 0
        self.msg_tfStamped.transform.translation.y = 0
        self.msg_tfStamped.transform.translation.z = 0
        self.msg_tfStamped.transform.rotation.x = 0.0
        self.msg_tfStamped.transform.rotation.y = 0.0
        self.msg_tfStamped.transform.rotation.z = 0.0
        self.msg_tfStamped.transform.rotation.w = 1.0

        msg_tf = tfMessage([self.msg_tfStamped])
        self.pub_tf.publish(msg_tf)
    
    def mainLoop(self):
        while rospy.is_shutdown() == False:
            self.loopRate.sleep()
            if(self.new_objMsg == True and self.new_depthMsg == True):
                self.msg_centroidPoint.point = self.calculate_3d_centroid(self.msg_obj.roi)
            self.SetupTfMsg()
            self.pub_cropped.publish(self.msg_cropped)
            self.pub_centroidPoint.publish(self.msg_centroidPoint)
    

if __name__ == '__main__':
    Extract3DCentroid(
    "/camera/depth/image_raw",
    "/utbots/vision/selected/object",
    43,
    57)

# #!/usr/bin/env python3

# import rospy
# from sensor_msgs.msg import Image, RegionOfInterest
# from vision_msgs.msg import Object, ObjectArray
# from geometry_msgs.msg import PointStamped, Point, TransformStamped
# from tf.msg import tfMessage
# from cv_bridge import CvBridge  
# import cv2
# # Math 
# import numpy as np
# from math import pow, sqrt, sin, tan, radians

# class Extract3DCentroid():
#     def __init__(self, topicDepthImg, topicObject, camFov_vertical, camFov_horizontal):
#         # Image FOV for trig calculations
#         self.camFov_vertical = camFov_vertical
#         self.camFov_horizontal = camFov_horizontal

#         # Messages
#         self.msg_tfStamped          = TransformStamped()
#         self.msg_cvDepthImg         = None
#         self.msg_roi                = RegionOfInterest()
#         self.msg_obj                = Object()
#         self.msg_centroidPoint      = PointStamped()
#         self.msg_centroidPoint.header.frame_id = "object_center"

#         # Flags
#         self.new_depthMsg = False
#         self.new_objMsg = False

#         # Subscribers
#         self.sub_depthImg = rospy.Subscriber(topicDepthImg, Image, self.callback_depthImg)
#         self.sub_object = rospy.Subscriber(topicObject, Object, self.callback_object)
        
#         self.pub_centroidPoint = rospy.Publisher(
#             "/utbots/vision/selected/objectPoint", PointStamped, queue_size=1)
#         self.pub_tf = rospy.Publisher(
#             "/tf", tfMessage, queue_size=10)
        
#         # Cv
#         self.cvBridge = CvBridge()
        
#         rospy.init_node("extract_3d_centroid", anonymous=True)

#         # Time
#         self.loopRate = rospy.Rate(50)
#         self.mainLoop()

#     def callback_depthImg(self, msg):
#         self.msg_cvDepthImg = self.cvBridge.imgmsg_to_cv2(msg, "32FC1")
#         self.new_depthMsg = True

#     def callback_object(self, msg):
#         self.msg_obj = msg
#         self.new_objMsg = True

#     def movingAverage(self, new_value, current_mean, n_values):
#         return current_mean+(new_value-current_mean)/n_values
    
#     def quarterFrameAverage(self, subframe, ver_start, ver_stop, ver_step, hor_start, hor_stop, hor_step):
#         # Iterates through the image from the start to the stop indexes, using the step defined
#         for i in range(ver_start, ver_stop, ver_step):
#             for j in range(hor_start, hor_stop, hor_step):
#                 # First point evaluated
#                 if i == ver_start and j == hor_start:
#                     subframe_mean = subframe[i][j]
#                     n_values = 1
#                 # If the pixel value diference to the mean is less than 100mm (10cm), adds to the mean
#                 elif subframe[i][j] - subframe_mean < 100:
#                     print(subframe[i][j] - subframe_mean)
#                     n_values += 1
#                     subframe_mean = self.movingAverage(subframe[i][j], subframe_mean, n_values)
#         return subframe_mean

#     def getMeanDistance(self):
#         # Frame dimensions
#         height = self.msg_obj.roi.height
#         width = self.msg_obj.roi.width

#         # Stores the point distances of every point inside the object's region of interest

#         # Divide the total frame into 4 subframes
#         btm_left =  self.msg_cvDepthImg[0:(height//2)        , 0:(width//2)      ]
#         top_left =  self.msg_cvDepthImg[(height//2+1):height , 0:(width//2)      ]
#         btm_right = self.msg_cvDepthImg[0:(height//2)        , (width//2+1):width]
#         top_right = self.msg_cvDepthImg[(height//2+1):height , (width//2+1):width]

#         # Calculates the average of all 4 subframes
#         btm_left_mean =  self.quarterFrameAverage(btm_left, len(btm_left)-1, -1, -1, len(btm_left[0])-1, -1, -1,)
#         top_left_mean =  self.quarterFrameAverage(top_left, 0, len(top_left), 1, len(btm_left[0])-1, -1, -1)
#         btm_right_mean = self.quarterFrameAverage(btm_right, len(btm_right)-1, -1, -1, 0, len(btm_right[0]), 1)
#         top_right_mean = self.quarterFrameAverage(top_right, 0, len(top_right), 1, 0, len(top_right[0]), 1)

#     def calculate_3d_centroid(self, roi):
#         mean_y = roi.y_offset + roi.height//2
#         mean_x = roi.x_offset + roi.width//2
#         return self.get3dPointFromDepthPixel(Point(mean_x, mean_y, 0), self.getMeanDistance())
    
#     # By using rule of three and considering the FOV of the camera: Calculates the 3D point of a depth pixel '''
#     def get3dPointFromDepthPixel(self, pixel, distance):
#         # Set the height and width of the parent image (camera)
#         width  = self.msg_obj.parent_img.width
#         height = self.msg_obj.parent_img.height

#         # Centralize the camera reference at (0,0,0)
#         ## (x,y,z) are respectively horizontal, vertical and depth
#         ## Theta is the angle of the point with z axis in the zx plane
#         ## Phi is the angle of the point with z axis in the zy plane
#         ## x_max is the distance of the side border from the camera
#         ## y_max is the distance of the upper border from the camera
#         theta_max = self.camFov_horizontal/2 
#         phi_max = self.camFov_vertical/2
#         x_max = width/2.0
#         y_max = height/2.0
#         x = (pixel.x/width) - x_max
#         y = (pixel.y/height) - y_max

#         # Caculate point theta and phi
#         theta = radians(theta_max * x / x_max)
#         phi = radians(phi_max * y / y_max)

#         # Convert the spherical radius rho from Kinect's mm to meter
#         rho = distance/1000

#         # Calculate x, y and z
#         y = rho * sin(phi)
#         x = sqrt(pow(rho, 2) - pow(y, 2)) * sin(theta)
#         z = x / tan(theta)

#         # z = (rho / sqrt(1 + pow(tan(theta), 2) + pow(tan(phi), 2)))
#         # x = z * tan(theta)
#         # y = z * tan(phi)

#         # # Corrections
#         # x = -x
#         # y = -y

#         return Point(x, y, z)
    
#     # Transformation tree methods
#     def SetupTfMsg(self):
#         self.msg_tfStamped.header.frame_id = "camera_link"
#         self.msg_tfStamped.header.stamp = rospy.Time.now()
#         self.msg_tfStamped.child_frame_id = "object_center"
#         self.msg_tfStamped.transform.translation.x = 0
#         self.msg_tfStamped.transform.translation.y = 0
#         self.msg_tfStamped.transform.translation.z = 0
#         self.msg_tfStamped.transform.rotation.x = 0.0
#         self.msg_tfStamped.transform.rotation.y = 0.0
#         self.msg_tfStamped.transform.rotation.z = 0.0
#         self.msg_tfStamped.transform.rotation.w = 1.0

#         msg_tf = tfMessage([self.msg_tfStamped])
#         self.pub_tf.publish(msg_tf)
    
#     def mainLoop(self):
#         while rospy.is_shutdown() == False:
#             self.loopRate.sleep()
#             if(self.new_objMsg == True and self.new_depthMsg == True):
#                 self.msg_centroidPoint.point = self.calculate_3d_centroid(self.msg_obj.roi)
#             self.SetupTfMsg()
#             self.pub_centroidPoint.publish(self.msg_centroidPoint)
    

# if __name__ == '__main__':
#     Extract3DCentroid(
#     "/camera/depth/image_raw",
#     "/utbots/vision/selected/object",
#     43,
#     57)
