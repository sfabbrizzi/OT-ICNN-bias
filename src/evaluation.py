from __future__ import print_function

from src.optimal_transport_modules.icnn_modules import *

from src.utils import get_iccns
import numpy as np
import torch.utils.data
import src.datasets
import os

def compute_optimal_transport_map(y, convex_g):
    """
    This function computes the OT map, which is the gradient of the function
    convex_g computed in y.
    """

    g_of_y = convex_g(y).sum()

    grad_g_of_y = torch.autograd.grad(g_of_y, y, create_graph=True)[0]

    return grad_g_of_y

def load_data(cfg):
    """
    ONLY for experiments on CelebA.

    Given the Hydra configuration of the training script, it returns the two
    dataset to compute the quadratic Wasserstein distance of.
    """

    # retrieves the name of the biased dataset.
    dataset = cfg.data.dataset_x.split("/")[2]
    # load biased dataset.
    X_data = src.datasets.CelebA_Features(
        cfg.data.dataset_x,
        "../data/{}/{}".format(dataset,
                               cfg.data.features))

    # load uniform dataset
    Y_data = src.datasets.CelebA_Features_Kernel(
        cfg.data.dataset_y,
        "../data/{}/{}".format(
            dataset,
            cfg.data.features),
        var=cfg.data.kernel_variance)

    return X_data, Y_data


def load_iccns(results_save_path, cfg, epoch_to_test):
    """
    It loads the correct ICCNs for a given configuration.
    """

    model_save_path = os.path.join(results_save_path, "storing_models")

    convex_f, convex_g = get_iccns(
        cfg.iccn.num_layers,
        cfg.iccn.full_quadratic,
        cfg.iccn.input_dim,
        cfg.iccn.num_neuron,
        cfg.iccn.activation)

    convex_f.load_state_dict(
        torch.load(model_save_path + '/convex_f_epoch_{}.pt'.format(epoch_to_test)))
    convex_g.load_state_dict(
        torch.load(model_save_path + '/convex_g_epoch_{}.pt'.format(epoch_to_test)))

    convex_f.eval()
    convex_g.eval()

    return convex_f, convex_g


def compute_OT_loss(X_data, Y_data, convex_f, convex_g, cuda = True):
    """
    ONLY for experiments on CelebA.

    Given the optimal convex_f and convex_g, Optimal Transport loss.
    """

    Y_loader = torch.utils.data.DataLoader(Y_data,
                                       batch_size=1)
    OT_loss = list()
    for batch, ids, _, _, _ in Y_loader:

        if cuda:
            batch = batch.cuda()

        batch.requires_grad = True

        grad_g_of_batch = compute_optimal_transport_map(batch, convex_g)

        f_grad_g_batch = convex_f(grad_g_of_batch)
        dot_prod = (grad_g_of_batch * batch).sum()

        loss_g = f_grad_g_batch - dot_prod
        OT_loss.append(loss_g.item() + .5 * batch.pow(2).sum().item())

    X_loader = torch.utils.data.DataLoader(X_data,
                                           batch_size=1,
                                           shuffle=True)
    f_values = list()
    for batch, ids, _, _ in X_loader:

        if cuda:
            batch = batch.cuda()

        f_values.append(.5 * batch.pow(2).sum().item() - convex_f(batch).item())

    return np.array(OT_loss).mean() + np.array(f_values).mean()

def compute_w2_Kantorovich(X_data, Y_data, convex_f, convex_g, cuda=True):
    """
    ONLY for experiments on CelebA.

    Given the optimal convex_f and Convex_g, quadratic Wasserstein distance
    as in the Kantorovich problem.
    """

    Y_loader = torch.utils.data.DataLoader(Y_data,
                                               batch_size=1)
    g_values = list()
    for batch, ids, _, _, _ in Y_loader:

        if cuda:
            batch = batch.cuda()

        g_values.append(.5 * batch.pow(2).sum().item() - convex_g(batch).item())

    X_loader = torch.utils.data.DataLoader(X_data,
                                            batch_size=1,
                                            shuffle=True)
    f_values = list()
    for batch, ids, _, _ in X_loader:

        if cuda:
            batch = batch.cuda()

        f_values.append(.5 * batch.pow(2).sum().item() - convex_f(batch).item())

    return np.array(g_values).mean() + np.array(f_values).mean()


def compute_w2_Monge(Y_data, convex_g, cuda=True):
    """
    ONLY for experiments on CelebA.

    Given the optimal convex_g, quadratic Wasserstein distance
    as in the monge problem.
    """
    Y_loader = torch.utils.data.DataLoader(Y_data,
                                           batch_size=1)
    w2 = list()
    for y, ids, _, _, _ in Y_loader:

        if cuda:
            y = y.cuda()

        y.requires_grad = True
        grad_g_of_y = compute_optimal_transport_map(y, convex_g)

        w2.append(.5 * (y - grad_g_of_y).pow(2).sum().item())

    return np.array(w2).mean()


def compute_convex_conjugate_loss(Y_data, convex_f, convex_g, cuda=True):
    """
    ONLY for experiments on CelebA.
    """
    Y_loader = torch.utils.data.DataLoader(Y_data,
                                        batch_size=1)
    loss = list()
    for y, ids, _, _, _ in Y_loader:

        if cuda:
            y = y.cuda()

        y.requires_grad = True

        grad_g_of_y = compute_optimal_transport_map(y, convex_g)
        grad_f_grad_g_of_y = compute_optimal_transport_map(grad_g_of_y, convex_f)

        loss.append(torch.norm(y - grad_f_grad_g_of_y, 2).item())

    return np.array(loss).mean()
