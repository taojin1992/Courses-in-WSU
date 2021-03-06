import h5py
import numpy as np
import random
import os.path
import math
#import ipdb
from skimage.measure import label
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from skimage.color.colorlabel import label2rgb
from data_reader import *
import skimage as skimage
from skimage import transform, color, exposure
def check_cornerInbox(source_box,target_box):
	boxB= source_box
	boxA=target_box
	corners_of_boxB=[(boxB[0],boxB[1]),(boxB[0],boxB[3]),(boxB[2],boxB[1]),(boxB[2],boxB[3])]
	is_intersect =False
	for corner in corners_of_boxB:
		x=corner[0]
		y=corner[1]
		if x >= boxA[0] and x<=boxA[2] and y>=boxA[1] and y<=boxA[3]:
			is_intersect = True
			break
	return is_intersect
def check_bbox_intersection(bboxA,bboxB):
	aXs=[bboxA[0],bboxA[2]]
	aYs=[bboxA[1],bboxA[3]]

	bXs=[bboxB[0],bboxB[2]]
	bYs=[bboxB[1],bboxB[3]]

	if max(aXs)<min(bXs) or min(aXs)>max(bXs) or max(aYs)<min(bYs) or min(aYs)>max(bYs):
		return False
	else:
		return True

def bb_intersection_over_union(boxA, boxB):
 		# This function code is modified based on code from http://www.pyimagesearch.com/2016/11/07/intersection-over-union-iou-for-object-detection/
		# determine the (x, y)-coordinates of the intersection rectangle
		# ipdb.set_trace()

		# if not (check_cornerInbox(boxA,boxB) or check_cornerInbox(boxB,boxA)):
		# 	return 0
		# ipdb.set_trace()
		if not check_bbox_intersection(boxA,boxB):
			return 0
		xA = max(boxA[0], boxB[0])
		yA = max(boxA[1], boxB[1])
		xB = min(boxA[2], boxB[2])
		yB = min(boxA[3], boxB[3])
	 
		# compute the area of intersection rectangle
		interArea = (xB - xA + 1) * (yB - yA + 1)
		# ipdb.set_trace()
	 
		# compute the area of both the prediction and ground-truth
		# rectangles
		boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
		boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)
	 
		# compute the intersection over union by taking the intersection
		# area and dividing it by the sum of prediction + ground-truth
		# areas - the interesection area
		# iou = interArea / float(boxAArea + boxBArea - interArea)
		iou = interArea / float(boxAArea + boxBArea -interArea)
	 
		# return the intersection over union value
		return iou
def index_of_largest_IOU(input_bbox,all_bbox):
	max_iou=0
	index  = -1
	i_bbox=[input_bbox[0][0],input_bbox[0][1],input_bbox[1][0],input_bbox[1][1]]
	for i,each_box in enumerate(all_bbox):
		# ipdb.set_trace()
		box=[each_box[0][0],each_box[0][1],each_box[1][0],each_box[1][1]]
		iou=bb_intersection_over_union(i_bbox,box)
		if max_iou< iou:
			max_iou=iou
			index = i
	return index
def bbox_to_4_scaler_list(bbox):
	return [bbox[0][0],bbox[0][1],bbox[1][0],bbox[1][1]]
def deform_bbox(bbox,x_size,y_size,dx1,dy1,dx2,dy2):
	# print('dx1={}  dx2={}'.format(dx1,dx2))
	# print('dy1={}  dy2={}'.format(dy1,dy2))
 	assert(abs(dx1)==abs(dx2))
 	assert(abs(dy1)==abs(dy2))
 	if bbox[0][0]+dx1 <0:
 		if dx1==dx2:
 			dx2=-bbox[0][0]
 		dx1=-bbox[0][0]
 	if bbox[1][0]+dx2>x_size-1:
 		if dx1==dx2:
 			dx1=x_size-bbox[1][0]-1
 		dx2=x_size-bbox[1][0]-1
 	if bbox[0][1]+dy1 <0:
 		if dy1==dy2:
 			dy2=-bbox[0][1]
 		dy1=-bbox[0][1]
 	if bbox[1][1]+dy2>y_size-1:
 		if dy1==dy2:
 			dy1=y_size-bbox[1][1]-1
 		dy2=y_size-bbox[1][1]-1 

 	new_bbox=[[bbox[0][0]+dx1,bbox[0][1]+dy1],[bbox[1][0]+dx2,bbox[1][1]+dy2]]
 	return new_bbox
def warp_image(image, bbox):
	x_size=image.shape[0]
	y_size=image.shape[1]
	if (bbox[1][0]>=x_size):
		print("bbox",bbox)
		print("x_size",x_size)
	
	if (bbox[1][1]>=y_size):
		print("bbox",bbox)
		print("y_size",y_size)
	
	assert(bbox[1][0]<x_size)

	assert(bbox[1][1]<y_size)
	warp_im = image[bbox[0][0]:bbox[1][0],bbox[0][1]:bbox[1][1]]
	return warp_im

def relabel_disconnected_seglabel(seg_label):
	unique_objs=np.unique(seg_label)
	unique_objs=unique_objs[np.nonzero(unique_objs)] # remove label 0 --neuron boundary
	unique_objs=np.sort(unique_objs)
 	
	# all_box=env.all_bbox.values()
	# all_labels=env.all_bbox.keys()
		# idx=np.where(seg_label==all_keys[3])
	max_lb=unique_objs[-1]+1
	for lb in unique_objs:
		zero_image=np.zeros_like(seg_label)
		zero_image[seg_label==lb]=1
		lbs=label(zero_image)
		unum=np.unique(lbs)
		if len(unum)>2:
			for l in unum[1:]:
				seg_label[lbs==l]=max_lb
				max_lb+=1
	return seg_label




class object_localization_env(object):
	def __init__(self,warp_multi_images=False):
		self.data_obj =None
		self.init_box_x_range = [100,150]
		self.init_box_y_range = [100,150]
		self.cur_bbox =None
		self.objective_bbox =None
		self.action_alpha=0.15
		self.previous_IOU = None
		self.tal =  0.6
		self.eta =  3.0 
#		self.fig,self.ax =plt.subplots(1)
		self.warp_multi_images=warp_multi_images
	def getName(self):
 		return 'base_env'
	def show_step(self):
		bbox=self.cur_bbox
		image =self.cur_image
		# seg_label=env.seg_label
		# zero_image=np.zeros_like(seg_label)
		# all_box=env.all_bbox.values()
		# zero_image[seg_label==486]=1
		# cur_g=seg_label
		# cur_g=zero_image
		# label_rgb_im=label2rgb(cur_g)
		# label_rgb_im=np.transpose(label_rgb_im,axes=[1,0,2])
		# print (warp_x.shape)
		# 
		# image =np.transpose(image)
		#self.ax.clear()
		#self.ax.imshow(image,cmap='gray')
		# ax.imshow(label_rgb_im,cmap='gray')
		# ax=plt.imshow(image,cmap='gray')
		ppxy,w,h=conver_bbox_to_xy_width_height(bbox)
		ppxy_o,w_o,h_o=conver_bbox_to_xy_width_height(self.objective_bbox)
		move_rect = patches.Rectangle(ppxy,w,h,linewidth=3,edgecolor='w',facecolor='none')
		obj_rect =  patches.Rectangle(ppxy_o,w_o,h_o,linewidth=2,edgecolor='g',facecolor='none')
		self.ax.add_patch(move_rect)
		self.ax.add_patch(obj_rect)
		plt.draw()
		# plt.show()
		plt.pause(0.00001)
	def localization_step(self,action):
		self.step_counts+=1
		if action != 8:
 			# ipdb.set_trace()
			self.update_current_bbox_with_action(action)
 			# iou_with_objective =bb_intersection_over_union(bbox_to_4_scaler_list(self.cur_bbox),bbox_to_4_scaler_list(self.objective_bbox))
 			# ipdb.set_trace()
			reward,iou_with_objective = self.get_reward()
		else:
 			# for trigger action
			iou_with_objective =bb_intersection_over_union(bbox_to_4_scaler_list(self.cur_bbox),bbox_to_4_scaler_list(self.objective_bbox))
			reward = self.eta if  iou_with_objective > self.tal else -1*self.eta
		if action==8 or iou_with_objective ==0 or self.step_counts >60:

			terminal = True
			self.init_starting_box()
		else:
			terminal = False
		if iou_with_objective ==0:
			print('terminated loc as IOU ==0')
		bbox_warp_image =self.get_cur_bbox_warp_image()#.astype(int)
		if self.warp_multi_images:
 			surrounding_image_list =self.get_largerCenter_and_surrounding_warp_images()
 			surrounding_image_list.append(bbox_warp_image)
 			# ipdb.set_trace()
 			if len(bbox_warp_image.shape)<=2:
 				bbox_warp_image=np.dstack(surrounding_image_list)
 			else:
 				bbox_warp_image=np.concatenate(surrounding_image_list,axis=2)

		return bbox_warp_image,reward, terminal
 
	def get_reward(self):
 		cur_iou = bb_intersection_over_union(bbox_to_4_scaler_list(self.objective_bbox),bbox_to_4_scaler_list(self.cur_bbox))
 		reward = 1 if (cur_iou -self.previous_IOU)>0 else -1
 		self.previous_IOU =cur_iou
 		return reward,cur_iou

	def update_current_bbox_with_action(self,action):
 		alpha_w = int(round(self.action_alpha *(self.cur_bbox[1][0]-self.cur_bbox[0][0])))
 		alpha_h = int(round(self.action_alpha *(self.cur_bbox[1][1]-self.cur_bbox[0][1])))
 		if action == 0:
 			# move left
 			# self.cur_bbox = [[int(round(self.cur_bbox[0][0]-alpha_w)),self.cur_bbox[1][0]],
 			# 				[int(round(self.cur_bbox[1][0]-alpha_w)),self.cur_bbox[1][0]]]
 			dx1=-alpha_w
 			dy1=0
 			dx2=-alpha_w
 			dy2=0
 		elif action ==1:
 			#move right
 			# self.cur_bbox = [[int(round(self.cur_bbox[0][0]+alpha_w)),self.cur_bbox[1][0]],
 							# [self.cur_bbox[1][0]+alpha_w,self.cur_bbox[1][0]]]
 			dx1=alpha_w
 			dy1=0
 			dx2=alpha_w
 			dy2=0
 		elif action ==2:
 			#move up
 			# self.cur_bbox = [[self.cur_bbox[0][0],int(round(self.cur_bbox[0][1]-alpha_h))],
 			# 				[self.cur_bbox[1][0],int(round(self.cur_bbox[1][1]-alpha_h))]]
 			dx1=0
 			dy1=-alpha_h
 			dx2=0
 			dy2=-alpha_h
 		elif action ==3:
 			#move_down
 			# self.cur_bbox = [[self.cur_bbox[0][0],int(round(self.cur_bbox[0][1]+alpha_h))],
 			# 				[self.cur_bbox[1][0],int(round(self.cur_bbox[1][1]+alpha_h))]]
 			dx1=0
 			dy1=alpha_h
 			dx2=0
 			dy2=alpha_h
 		elif action ==4:
 			#bigger
 			# self.cur_bbox =[[int(round(self.cur_bbox[0][0]-alpha_w/2)),int(round(self.cur_bbox[1][0]-alpha_h/2))],
 			# 				[int(round(self.cur_bbox[1][0]+alpha_w/2)),int(round(self.cur_bbox[1][0]+alpha_h/2))]]
 			dx1=int(round(-alpha_w/2.0))
 			dy1=int(round(-alpha_h/2.0))
 			dx2=int(round(alpha_w/2.0))
 			dy2=int(round(alpha_h/2.0))
 		elif action ==5:
 			#smaller
 			# self.cur_bbox =[[int(round(self.cur_bbox[0][0]+alpha_w/2)),int(round(self.cur_bbox[1][0]+alpha_h/2))],
 			# 				[int(round(self.cur_bbox[1][0]-alpha_w/2)),int(round(self.cur_bbox[1][0]-alpha_h/2))]]
 			dx1=int(round(alpha_w/2.0))
 			dy1=int(round(alpha_h/2.0))
 			dx2=int(round(-alpha_w/2.0))
 			dy2=int(round(-alpha_h/2.0))
 		elif action ==6:
 			# fatter 
 			# self.cur_bbox =[[self.cur_bbox[0][0],int(round(self.cur_bbox[1][0]+alpha_h/2))],
 							# [self.cur_bbox[1][0],int(round(self.cur_bbox[1][0]-alpha_h/2))]]
 			dx1=0
 			dy1=int(round(alpha_h/2))
 			dx2=0
 			dy2=-dy1
 		elif action ==7:
 			# Taller
 			# self.cur_bbox =[[int(round(self.cur_bbox[0][0]+alpha_w/2)),self.cur_bbox[1][0]+alpha_h/2],
 							# [int(round(self.cur_bbox[1][0]-alpha_w/2)),self.cur_bbox[1][0]-alpha_h/2]]
 			dx1=int(round(alpha_w/2))
 			dy1=0
 			dx2=-dx1
 			dy2=0
 		elif action==8:
 			# trigger
 			dx1=0
 			dy1=0
 			dx2=0
 			dy2=0
 		self.cur_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

	def get_largerCenter_and_surrounding_warp_images(self):
		bbox_width =self.cur_bbox[1][0]-self.cur_bbox[0][0]
		bbox_height =self.cur_bbox[1][1]-self.cur_bbox[0][1]
		dx2=dx1=-int(round((bbox_width)/2.0))
		dy2=dy1=-int(round((bbox_height)/2.0))
		topleft_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx2=dx1=int(round((bbox_width)/2.0))
		dy2=dy1=-int(round((bbox_height)/2.0))
		topright_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx2=dx1=-int(round((bbox_width)/2.0))
		dy2=dy1=int(round((bbox_height)/2.0))
		bootomleft_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx2=dx1=int(round((bbox_width)/2.0))
		dy2=dy1=int(round((bbox_height)/2.0))
		bootomright_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx1=-int(round((bbox_width)*0.1))
		dy1=-int(round((bbox_height)*0.1))
		dx2 =dx1*-1
		dy2=dy1*-1
		# dx2=int(round((bbox_width)*0.1))
		# dy2=int(round((bbox_height)*0.1))
		centerlager_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)
		warp_image_list =[]
		warp_image_list.append(warp_image(self.cur_image,topleft_bbox))
		warp_image_list.append(warp_image(self.cur_image,topright_bbox))
		warp_image_list.append(warp_image(self.cur_image,topright_bbox))
		warp_image_list.append(warp_image(self.cur_image,topleft_bbox))
		large_image=warp_image(self.cur_image,centerlager_bbox)
		large_image=skimage.transform.resize(large_image,(bbox_width,bbox_height))
		warp_image_list.append(large_image)
		return warp_image_list

class nature_object_env(object_localization_env):
	def __init__(self,warp_multi_images=False):
		super(nature_object_env,self).__init__(warp_multi_images)
		self.data_obj=RL_data()
		self.init_starting_box()
		print("init")
	def getName(self):
		return 'nature_localization_env'
	def read_one_image(self):
		image,all_bbox = self.data_obj.get_natural_image_with_boundingBox()
		self.all_bbox	=	all_bbox
		self.x_size 	=	image.shape[0]
		self.y_size 	=	image.shape[1]
		self.cur_image  =   image
		self.init_box_x_range = [int(math.floor(self.x_size*0.25)),int(math.floor(self.x_size*0.5))]
		self.init_box_y_range = [int(math.floor(self.y_size*0.25)),int(math.floor(self.y_size*0.5))]
	def get_random_start_bbox(self):
		x_left 			=	random.randint(0,self.x_size-self.init_box_x_range[1])
		width                   =	random.randint(self.init_box_x_range[0], self.init_box_x_range[1])
		x_right 		= 	x_left+width		
		y_top 			=	random.randint(0,self.y_size-self.init_box_y_range[1])
		y_bottom 		= 	y_top+width # make a square box
		self.cur_bbox 	=	[[x_left,y_top],[x_right,y_bottom]]

	def init_starting_box(self):
		self.read_one_image()
		# ipdb.set_trace()
		self.step_counts =0

		# ipdb.set_trace()
		all_box_list = self.all_bbox.values()
		print("all_box_list",all_box_list)
		all_box_keys = self.all_bbox.keys()
		print("all_box_keys",all_box_keys)
		cont =0
		while True:
			self.get_random_start_bbox()
			idx=index_of_largest_IOU(self.cur_bbox,all_box_list)
			cont+=1
			if idx >-1:
				break
			if cont>100:
				self.read_one_image()
				all_box_list = self.all_bbox.values()
				print("all_box_list",all_box_list)
				all_box_keys = self.all_bbox.keys()
				print("all_box_keys",all_box_keys)
				cont=0

		print("finish compute largest iou")

		self.objective_bbox =self.all_bbox[idx]
		# ipdb.set_trace()
		self.previous_IOU   = bb_intersection_over_union(bbox_to_4_scaler_list(self.cur_bbox),
														bbox_to_4_scaler_list(self.objective_bbox))
	def get_cur_bbox_warp_image(self):
		return  warp_image(self.cur_image,self.cur_bbox)


class neuron_object_env(object_localization_env):
	def __init__(self):
		super(neuron_object_env,self).__init__()
		self.data_obj=RL_neuron_data()
		
		self.init_starting_box()
	def getName(self):
		return 'neuron_localization_env'
	def read_one_image(self):
		slice_idx =0
		image,seg_label,all_bbox  =	self.data_obj.get_image_with_boundingBox(slice_idx)
		# ipdb.set_trace()
		self.all_bbox	=	all_bbox
		self.seg_label  =   seg_label
		self.x_size 	=	image.shape[0]
		self.y_size 	=	image.shape[1]
		self.cur_image  =   image
		self.transposed_image =np.transpose(image)
	def get_random_start_bbox(self):
		x_left 			=	random.randint(0,self.x_size-self.init_box_x_range[1])
		x_right 		= 	x_left+random.randint(self.init_box_x_range[0], self.init_box_x_range[1])
		y_top 			=	random.randint(0,self.y_size-self.init_box_y_range[1])
		y_bottom 		= 	y_top+random.randint(self.init_box_y_range[0], self.init_box_y_range[1])
		self.cur_bbox 	=	[[x_left,y_top],[x_right,y_bottom]]
	def find_center_label(self,bbox):
		cent_x= int(round(bbox[0] + (bbox[2]-bbox[0])/2.0))
		cent_y= int(round(bbox[1] + (bbox[3]-bbox[1])/2.0))
		lb=self.seg_label[cent_x,cent_y]
		while lb==0:
			n_x= cent_x+random.randrange(-15,15)
			n_y= cent_y+random.randrange(-15,15)
			lb=self.seg_label[n_x,n_y]
		return lb

	def init_starting_box(self):
		
		# ipdb.set_trace()
		self.read_one_image()
		self.step_counts =0
		# ipdb.set_trace()
		all_box_list = self.all_bbox.values()
		all_box_keys = self.all_bbox.keys()
		self.get_random_start_bbox()
		lb=self.find_center_label(bbox_to_4_scaler_list(self.cur_bbox))
		self.objective_bbox =self.all_bbox[lb]
		# while True:
		# 	self.get_random_start_bbox()
		# 	idx=index_of_largest_IOU(self.cur_bbox,all_box_list)
		# 	if idx >-1:
		# 		break
		# self.objective_bbox =all_box_list[idx]
		# largest_lb=all_box_keys[idx]
		# ipdb.set_trace()
		self.previous_IOU   = bb_intersection_over_union(bbox_to_4_scaler_list(self.cur_bbox),
														bbox_to_4_scaler_list(self.objective_bbox))
	def get_cur_bbox_warp_image(self):
		return  warp_image(self.cur_image,self.cur_bbox)
	def get_largerCenter_and_surrounding_warp_images(self):
		bbox_width =self.cur_bbox[1][0]-self.cur_bbox[0][0]
		bbox_height =self.cur_bbox[1][1]-self.cur_bbox[0][1]
		dx2=dx1=-int(round((bbox_width)/2.0))
		dy2=dy1=-int(round((bbox_heigt)/2.0))
		topleft_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx2=dx1=int(round((bbox_width)/2.0))
		dy2=dy1=-int(round((bbox_heigt)/2.0))
		topright_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx2=dx1=-int(round((bbox_width)/2.0))
		dy2=dy1=int(round((bbox_heigt)/2.0))
		bootomleft_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx2=dx1=int(round((bbox_width)/2.0))
		dy2=dy1=int(round((bbox_heigt)/2.0))
		bootomright_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		dx1=-int(round((bbox_width)*0.1))
		dy1=-int(round((bbox_heigt)*0.1))
		dx2=int(round((bbox_width)*0.1))
		dy1=int(round((bbox_heigt)*0.1))
		centerlager_bbox=deform_bbox(self.cur_bbox,self.x_size,self.y_size,dx1,dy1,dx2,dy2)

		warp_image_list =[]
		warp_image_list.append(warp_image(self.cur_image,topleft_bbox))
		warp_image_list.append(warp_image(self.cur_image,topright_bbox))
		warp_image_list.append(warp_image(self.cur_image,topright_bbox))
		warp_image_list.append(warp_image(self.cur_image,topleft_bbox))
		warp_image_list.append(warp_image(self.cur_image,centerlager_bbox))
		return warp_image_list

class RL_data(object):
	def __init__(self):
		super(RL_data,self).__init__()
		self.Annotations_list,self.image_list=get_data()
	def getName(self):
		return 'Nature_data'
	def get_natural_image_with_boundingBox(self):
		max_num = 19
		index = random.randint(19, max_num)
		Annotations=self.Annotations_list[index]
		images = self.image_list[index]
		self.x_size = images.shape[0]
		self.y_size = images.shape[1]
		self.z_size = images.shape[2]
		print("label",Annotations)
		obj_bbox = {}
		for i in range(len(Annotations)):
			obj_bbox[i] = Annotations[i]
		return images, obj_bbox

class RL_neuron_data(RL_data):
	def __init__(self):
		super(RL_neuron_data,self).__init__()
		self.data_file='./data/snemi3d_train_full_stacks_added_segLabel_v1_scaled.h5'

		h5f=h5py.File(self.data_file,'r')
		self.images=h5f['data']
		self.seg_labels=h5f['seg_label']
		self.x_size=self.images.shape[0]
		self.y_size=self.images.shape[1]
		self.z_size=self.images.shape[2]
	def getName(self):
 		return 'neuron_data'
	def get_image_with_boundingBox(self,slice_idx):
 		image,seg_label=	self.get_one_image(slice_idx)
 		seg_label      =	seg_label.astype(int)
 		seg_label      =	relabel_disconnected_seglabel(seg_label) # connected in 3D but diconnected in 2D
 		bbox           =	self.get_bounding_box(seg_label)
 		return image,seg_label,bbox
	def get_one_image(self,slice_idx):
 		image=self.images[:,:,slice_idx]
 		seg_label=self.seg_labels[:,:,slice_idx]
 		return image, seg_label
	def get_bounding_box(self,seg_label):
 		obj_bbox={}
 		unique_objs=np.unique(seg_label)
 		unique_objs=unique_objs[np.nonzero(unique_objs)] # remove label 0 --neuron boundary
 		for each_seg_lb in unique_objs:
 			# each_obj_idx=seg_label==each_seg_lb
 			seg_index = np.where(seg_label==each_seg_lb)
 			
 			left  	= min(seg_index[0])
 			right 	= max(seg_index[0])
 			top   	= min(seg_index[1])
 			bottom 	= max(seg_index[1])
 			# obj_bbox.append([(left,top),(right,bottom)])
 			obj_bbox[each_seg_lb]=([(left,top),(right,bottom)])
 			# ipdb.set_trace()
 		return obj_bbox
def conver_bbox_to_xy_width_height(bbox):
	x1=bbox[0][0]
	y1=bbox[0][1]
	width=bbox[1][0]-bbox[0][0]
	height=bbox[1][1]-bbox[0][1]
	return (x1,y1),width,height
def test_iou():
	bbox1=[2,2,4,4]
	bbox2=[8,8,15,15]
	iou=bb_intersection_over_union(bbox1,bbox2)
	# ipdb.set_trace()
	assert(iou<=0)

	bbox1=[2,2,8,8]
	bbox2=[6,6,15,15]
	iou=bb_intersection_over_union(bbox1,bbox2)
	# ipdb.set_trace()
	assert(iou>0)

	bbox1=[335,423,400,455]
	bbox2=[113,220,404,430]
	iou=bb_intersection_over_union(bbox1,bbox2)
	# ipdb.set_trace()
	assert(iou<=0)

def test_env():
	import matplotlib.pyplot as plt
	import matplotlib.patches as patches
	from skimage.color.colorlabel import label2rgb
	env = nature_object_env()
	fig,ax =plt.subplots(1)
	# fig2,ax2 =plt.subplots(1)
	action_discription={0:'left',1:'right',2:'up',3:'bottom',4:'bigger',5:'smaller',6:'fatter',7:'toller',8:'triger'}
	for i in range(100):
		action=random.randint(0,8)
		warp_x, reward, terminal=env.localization_step(action)
		#print('Action = {}'.format(action_discription[action]))
		bbox=env.cur_bbox
		image =env.cur_image
		#zero_image=np.zeros_like(seg_label)
		all_box=env.all_bbox.values()
		# cur_g=zero_image
		# print (warp_x.shape)
		# 
		ax.clear()
		#ax.imshow(image,cmap='gray')
		# ipdb.set_trace()
		#ax[1].clear()
		#ax[1].imshow(warp_x,cmap='gray')
		# ax.imshow(label_rgb_im,cmap='gray')
		# ax=plt.imshow(image,cmap='gray')
		ppxy,w,h=conver_bbox_to_xy_width_height(bbox)
		ppxy = (104, 45)
		w = 45
		h = 107
		ppxy_o = (108, 46)
		w_o = 45
		h_o = 105

		#ppxy_o,w_o,h_o=conver_bbox_to_xy_width_height(env.objective_bbox)
		print(ppxy_o)
		print(w_o)
		print(h_o)
		move_rect = patches.Rectangle(ppxy,w,h,linewidth=3,edgecolor='w',facecolor='none')
		obj_rect =  patches.Rectangle(ppxy_o,w_o,h_o,linewidth=3,edgecolor='r',facecolor='none')
		ax.add_patch(move_rect)
		ax.add_patch(obj_rect)
		label_name_infer = 0
		for bbox in env.all_bbox.values():
			ppxy,w,h=conver_bbox_to_xy_width_height(bbox)
			#ppxy = (120,97)
			#w = 27
			#h = 52
			each_rect = patches.Rectangle(ppxy,w,h,linewidth=1.5,edgecolor='g',facecolor='none')
			ax.add_patch(each_rect)
		#plt.show()
		#plt.savefig('test.png')
		print("finish save")

		plt.pause(5)

if __name__ == "__main__":
	# test_iou()
	test_env()
