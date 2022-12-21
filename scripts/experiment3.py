import argparse
import torch
import numpy as np

from hydra import initialize, compose
from torch import nn
from src.utils import get_iccns
from src.utils import set_random_seeds

class Dataset(nn.Module):

    def __init__(self, path, ground_truth = 1):
        super(Dataset, self).__init__()
        temp = np.load(path)
        temp = temp[temp[:,-1] == ground_truth]

        self.X = temp[:, :-1]
        self.y = temp[:,-1]

    def __len__(self):
        return self.y.shape[0]

    def __getitem__(self, item):
        self.X[item]
        return torch.from_numpy(self.X[item]), self.y[item]

def compute_optimal_transport_map(y, convex_g):
    y = y.float()
    g_of_y = convex_g(y).sum()

    grad_g_of_y = torch.autograd.grad(g_of_y, y, create_graph=True)[0]

    return grad_g_of_y

def load_iccns(cfg, epoch_to_test):

    dataset = cfg.data.dataset.split("/")[-1].split(".")[0]

    if cfg.training.optimizer == "SGD":
        results_save_path = ('../results/Experiment3/training/{0}/'
                             'input_dim_{1}/init_{2}/layers_{3}/neuron_{4}/'
                             'lambda_cvx_{5}_mean_{6}/optim_{7}lr_{8}momen_{13}/'
                             'gen_{9}/batch_{10}/trial_{11}_last_{12}_qudr').format(
            dataset,
            cfg.iccn.input_dim,
            cfg.iccn.initialization,
            cfg.iccn.num_layers,
            cfg.iccn.num_neuron,
            cfg.training.lambda_cvx,
            cfg.training.lambda_mean,
            cfg.training.optimizer,
            cfg.training.lr,
            cfg.training.n_generator_iters,
            cfg.training.batch_size,
            cfg.settings.trial,
            cfg.iccn.full_quadratic,
            cfg.training.momentum)
    elif cfg.training.optimizer == "Adam":
        results_save_path = ('../results/Experiment3/training/{0}/'
                             'input_dim_{1}/init_{2}/layers_{3}/neuron_{4}/'
                             'lambda_cvx_{5}_mean_{6}/optim_{7}lr_{8}betas_{13}_{14}/'
                             'gen_{9}/batch_{10}/trial_{11}_last_{12}_qudr').format(
            dataset,
            cfg.iccn.input_dim,
            cfg.iccn.initialization,
            cfg.iccn.num_layers,
            cfg.iccn.num_neuron,
            cfg.training.lambda_cvx,
            cfg.training.lambda_mean,
            cfg.training.optimizer,
            cfg.training.lr,
            cfg.training.n_generator_iters,
            cfg.training.batch_size,
            cfg.settings.trial,
            cfg.iccn.full_quadratic,
            cfg.training.beta1_adam,
            cfg.training.beta2_adam)
    elif cfg.training.optimizer == "RMSProp":
        results_save_path = ('../results/Experiment3/training/{0}/'
                             'input_dim_{1}/init_{2}/layers_{3}/neuron_{4}/'
                             'lambda_cvx_{5}_mean_{6}/optim_{7}lr_{8}momen{13}_alpha{14}/'
                             'gen_{9}/batch_{10}/trial_{11}_last_{12}_qudr').format(
            dataset,
            cfg.iccn.input_dim,
            cfg.iccn.initialization,
            cfg.iccn.num_layers,
            cfg.iccn.num_neuron,
            cfg.training.lambda_cvx,
            cfg.training.lambda_mean,
            cfg.training.optimizer,
            cfg.training.lr,
            cfg.training.n_generator_iters,
            cfg.training.batch_size,
            cfg.settings.trial,
            cfg.iccn.full_quadratic,
            cfg.training.momentum,
            cfg.training.alpha_rmsprop)

    model_save_path = results_save_path + '/storing_models'

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

    Y_loader = torch.utils.data.DataLoader(Y_data,
                                       batch_size=1)
    OT_loss = list()
    for batch, _ in Y_loader:

        batch = batch.float()
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
    for batch, _ in X_loader:
        batch = batch.float()

        if cuda:
            batch = batch.cuda()

        f_values.append(.5 * batch.pow(2).sum().item() - convex_f(batch).item())

    return np.array(OT_loss).mean() + np.array(f_values).mean()

def compute_Kantorovich_potential(x, convex_f):
    x = x.float()
    return (.5*x.pow(2).sum() - convex_f(x)).item()

def main():
    with initialize(version_base=None,
                    config_path="../scripts/outputs/{}/.hydra".format(args.config)):

        set_random_seeds(cfg.settings.seed)

        # load config
        cfg = compose(config_name="config")
        cuda = not cfg.settings.no_cuda and torch.cuda.is_available()

        # data
        dataset = cfg.data.dataset.split("/")[-1].split(".")[0]
        X_data = Dataset(
            cfg.data.dataset,
            ground_truth=0)

        Y_data = Dataset(
            cfg.data.dataset,
            ground_truth=1)

        # load iccns
        convex_f, convex_g = load_iccns(cfg, args.epoch)


        wasserstein = compute_OT_loss(X_data, Y_data, convex_f, convex_g, cuda)
        with open("../results/Experiment3/experiment3_wasserstein.tsv", "a") as f:
            f.write(cfg.data.dataset + "\t" + str(wasserstein) + "\n")

        X_loader = torch.utils.data.DataLoader(
                                    X_data,
                                    batch_size=1,
                                    shuffle=False)
        potentials = list()
        for x, _ in  X_loader:
            potentials.append(compute_Kantorovich_potential(x, convex_f))

        np.save("../results/Experiment3/{}_potentials.npy".format(dataset), np.array(potentials))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Experiment1')

    parser.add_argument('--config',
                        type=str,
                        default='',
                        help='configuration to use in the experiment')
    parser.add_argument('--epoch',
                        type=int,
                        default=1,
                        help='epoch checkpoint to load for the experiment')

    args = parser.parse_args()

    main()
