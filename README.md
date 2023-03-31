- ##### This stack contains vision related packages, such as:
    - darknet_ros
    - img_converter
    - mediapipe_track

- ## Getting started
    - ### Installation
        ```bash 
        cd catkin_ws/src
        git clone --recurse-submodules https://github.com/UtBotsAtHome-UTFPR/utbots_vision.git
        cd ../
        ```

    - ### Building
        ```bash
        catkin_make -DCMAKE_BUILD_TYPE=Release
        ```

    - ### Mediapipe dependencies
        - **Only for Jetson Nano + Ubuntu 18**
            - Install Python 3.9 and virtualenv
                ```bash
                sudo add-apt-repository ppa:deadsnakes/ppa # Repository with many Python versions
                sudo apt update
                sudo apt install python3.9 python3.9-venv -y
                python3.9 -m pip install virtualenv
                PY_LOCATION=$(which python3.9)
                roscd mediapipe_track/src
                python3.9 -m virtualenv venv --python=$PY_LOCATION # Create virtual env
                ```
            - You should **only use Mediapipe with the virtual Python executable**
                ```bash
                source venv/bin/activate    # Enter virtual env
                python --version            # Check Python version
                which python                # Check where Python executable is
                python locker_human.py      # Instead of "rosrun mediapipe_track locker_human.py"
                ```
        - **Pip requirements**
            ```bash
            roscd mediapipe_track/src
            python3 -m pip install -r requirements.txt
            ```
- ### Nodes
    - #### darknet_ros
        - **Description**
            - Darknet/YOLO + ROS
        - **Dependencies**
            - This software is built on the Robotic Operating System ([ROS]), which needs to be [installed](http://wiki.ros.org) first. Additionally, YOLO for ROS depends on following software:
                - [OpenCV](http://opencv.org/) (computer vision library),
                - [boost](http://www.boost.org/) (c++ library),
                - [freenect_launch](https://github.com/ros-drivers/freenect_stack) (kinect camera package)
        - **Running** 
            - Detailed information can be found in the [link](https://github.com/gustavo-fardo/darknet_ros)
            - **Webcam**
                ```bash
                roslaunch darknet_ros darknet_ros.launch
                ```
            - **Kinect V1**
                ```bash
                roslaunch darknet_ros kinect.launch
                ```
    - #### img_converter
        - **Description**
            - Changes the encoding of a sensor_msgs::Image to an opencv acceptable RGB8 format
        - **Dependencies**
            - This package depends on [OpenCV](http://opencv.org/) (computer vision library).
        - **Running**
            ```bash
            rosrun img_converter img_converter
            ```

        - **Topics**
            - **Subscribed Topics**
                - **`/camera/rgb/image_raw`** ([sensor_msgs/Image])
                    - The Kinect V1 camera image
            - **Published Topics**
                - **`/image_converter/output_video`** ([sensor_msgs/Image])
                    - The converted image to RBG8 encoding

    - #### mediapipe_track
        - **Description**
            - Applies the MediaPipe Pose solution (https://google.github.io/mediapipe/solutions/pose) with Kinect V1 images through ROS Topics and Nodes. An important addition to MediaPipe Pose is the ability to calculate and detect the person's 3D position and publish this information in ROS Topics so the robot can know its relative position from the person detected.
        - **Dependencies**
            - This package depends on [freenect_launch](https://github.com/ros-drivers/freenect_stack) and runs on python, with mediapipe library.
        - **Running**
            - First, run freenect
                ```bash
                roslaunch mediapipe_track freenect.launch
                ```
            - Then, to run the pose tracking and 3D position algorithm, run 
                ```bash
                roslaunch mediapipe_track locker_human.launch
                ```
