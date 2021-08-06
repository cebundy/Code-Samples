# Code-Samples
Sample code from past projects
These are scripts written in python 2.  I;ve since moved on to python 3.
MGCLD.py:
This is a class library which test connect to, monitor and control content 
director (cld) devices, in the storage server cluster.
The firmware runs embedded linux on which runs proprietary firmware which includes 
a filesystem that runs on top of ext3, replacing the ext3 journaling.  
This cld controls the tracking and storage of data fragments (variable sized
blocks of data) stored across the high availablily, high speed storage system. 
The cld is the main intelligence of the system that monitors and controls 
the different devices that make up that system

