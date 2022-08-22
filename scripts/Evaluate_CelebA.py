#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 22 13:55:17 2022

@author: simonefabrizzi
"""

from __future__ import print_function
import argparse
import torch
import torch.nn as nn
from src.optimal_transport_modules.icnn_modules import *
import facenet_pytorch as facenet
import numpy as np
import pandas as pd
import skimage
import torch.utils.data
import src.datasets
from src.utils import *
from torchvision import transforms
from torchvision.utils import make_grid
from PIL import Image
from sklearn.cluster import KMeans
from torchvision.models import resnet18, ResNet18_Weights

parser = argparse.ArgumentParser(description='PyTorch CelebA Toy Beard '
                                             'Experiment Evaluation')
parser.add_argument('--epoch',
                    type=int,
                    default=30,
                    metavar='S',
                    help='epoch to be evaluated')

parser.add_argument('--no-cuda',
                    action='store_true',
                    default=False,
                    help='disables CUDA')

parser.add_argument('--BATCH_SIZE',
                    type=int,
                    default=10,
                    help='size of the batches')

args = parser.parse_args()

args.cuda = not args.no_cuda and torch.cuda.is_available()
args.mps = torch.backends.mps.is_available()


def save_images_as_grid(path, array_img_vectors):

    array_img_vectors = torch.from_numpy(array_img_vectors)\
        .float().permute(0, 3, 1, 2)
    grid = make_grid(array_img_vectors, nrow=6, normalize=True)*255
    ndarr = grid.to('cpu', torch.uint8).numpy().T
    im = Image.fromarray(ndarr.transpose(1, 0, 2))

    im.save(path)


def compute_optimal_transport_map(y, convex_g):

    g_of_y = convex_g(y).sum()

    grad_g_of_y = torch.autograd.grad(g_of_y, y, create_graph=True)[0]

    return grad_g_of_y


results_save_path = ('../results/Results_CelebA_ResNet18/'
                     'input_dim_1000/init_trunc_inv_sqrt/layers_3/neuron_1024/'
                     'lambda_cvx_0.1_mean_0.0/'
                     'optim_Adamlr_0.001betas_0.5_0.99/'
                     'gen_16/batch_25/trial_1_last_inp_qudr')
model_save_path = results_save_path + '/storing_models'

df = pd.read_csv("../data/celeba/list_attr_celeba.csv")
df["values_resnet18"] = [None]*len(df)

features = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1).eval()
features.fc = nn.Identity()

transform = transforms.Compose([transforms.ToTensor(),
                                transforms.Resize(160)])

X_data = src.datasets.CelebA("../data/celeba/list_attr_celeba.csv",
                             "../data/celeba/Img_folder/Img",
                             transform=transform)
train_loader = torch.utils.data.DataLoader(X_data,
                                           batch_size=1)

convex_f = Simple_Feedforward_3Layer_ICNN_LastFull_Quadratic(512,
                                                             1024,
                                                             "leaky_relu")
convex_f.load_state_dict(
    torch.load(model_save_path + '/convex_f_epoch_{}.pt'.format(args.epoch)))
convex_f = convex_f.eval()

convex_g = Simple_Feedforward_3Layer_ICNN_LastFull_Quadratic(512,
                                                             1024,
                                                             "leaky_relu")
convex_g.load_state_dict(
    torch.load(model_save_path + '/convex_g_epoch_{}.pt'.format(args.epoch)))
convex_g = convex_g.eval()

if args.cuda:
    convex_f.cuda()
    features.cuda()
elif args.mps:
    convex_f.to("mps")
    features.to("mps")


features_list = list()
val_g = list()
for imgs, ids, _ in train_loader:
    ids = ids.item()
    if args.cuda:
        imgs = imgs.cuda()
    elif args.mps:
        imgs = imgs.to("mps")

    features_vector = features(imgs)
    
    features_list.append(features_vector.detach().cpu().numpy())

    if df.loc[ids, "Male"] == -1:
        val = convex_f(features_vector).item()
        df.loc[ids, "values_resnet18"] = val
    else:
        val = convex_g(features_vector).item()
        df.loc[ids, "values_resnet18"] = val

features_array = np.concatenate(features_list)
np.save(results_save_path + "feature_space.npy", features_array)

features_x = features_array[df["Male"] == -1]
features_y = features_array[df["Male"] == 1]

df[df["Male"] == -1].values_resnet18 = .5*(np.linalg.norm(features_x).mean())\
    - df[df["Male"] == -1].values_resnet18
df[df["Male"] == 1].values_resnet18 = .5*(np.linalg.norm(features_y).mean())\
    - df[df["Male"] == 1].values_resnet18

mean_val_y = df[df["Male"] == 1].values_resnet18.mean()
df[df["Male"] == -1].values_resnet18 += mean_val_y

df.to_csv("../data/celeba/list_attr_celeba.csv", index=False)

# =============================================================================
# img_ids = df.sort_values(by="values", ascending=False)["image_id"][:36]
# array_img_vectors = np.array(
#     [skimage.io.imread("../data/celeba/Img_folder/Img/" + file)
#      for file in img_ids])
# 
# path = results_save_path+'/grid_epoch_{}_female.jpeg'.format(args.epoch)
# save_images_as_grid(path, array_img_vectors)
# 
# img_ids = df.sort_values(by="values1", ascending=False)["image_id"][:36]
# array_img_vectors = np.array(
#     [skimage.io.imread("../data/celeba/Img_folder/Img/" + file)
#      for file in img_ids])
# 
# 
# path = results_save_path+'/grid_epoch_{}_female_value2.jpeg'.format(args.epoch)
# save_images_as_grid(path, array_img_vectors)
# 
# =============================================================================
# =============================================================================
# 
# ##################################################################
# # cluster the top 10% images
# last_decile = df[df["values"] >= np.percentile(df["values"], 90)]
# 
# last_decile = last_decile.reset_index()
# X_data = src.datasets.CelebA(None,
#                              "../data/celeba/Img_folder/Img",
#                              df=last_decile,
#                              transform=transform)
# 
# train_loader = torch.utils.data.DataLoader(X_data,
#                                            batch_size=args.BATCH_SIZE)
# 
# space = []
# for imgs, ids, _ in train_loader:
#     if args.cuda:
#         imgs = imgs.cuda()
# 
#     with torch.no_grad():
#         features_vector = features(imgs).cpu().numpy()
# 
#     space.append(features_vector)
# 
# space = np.concatenate(space)
# 
# kmeans = KMeans(4)
# kmeans.fit(space)
# 
# last_decile["cluster"] = kmeans.labels_
# last_decile.to_csv("../data/celeba/celebA_female_last_decile.csv", index=False)
# 
# =============================================================================
