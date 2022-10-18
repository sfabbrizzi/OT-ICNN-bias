import os
import torch
import torch.optim as optim
import random
import logging.config
import shutil
import numpy as np
import pandas as pd
from bokeh.io import output_file, save, show
from bokeh.plotting import figure
from bokeh.layouts import column
from src.optimal_transport_modules.icnn_modules import *

# from bokeh.charts import Line, defaults
#
# defaults.width = 800
# defaults.height = 400
# defaults.tools = 'pan,box_zoom,wheel_zoom,box_select,hover,resize,reset,save'


def setup_logging(log_file='log.txt'):
    """Setup logging configuration
    """
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        filename=log_file,
                        filemode='w')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


class ResultsLog(object):

    def __init__(self, path='results.csv', plot_path=None):
        self.path = path
        self.plot_path = plot_path or (self.path + '.html')
        self.figures = []
        self.results = None

    def add(self, **kwargs):
        df = pd.DataFrame([kwargs.values()], columns=kwargs.keys())
        if self.results is None:
            self.results = df
        else:
            self.results = pd.concat([self.results,df], ignore_index=True)

    def save(self, title='Training Results'):
        if len(self.figures) > 0:
            if os.path.isfile(self.plot_path):
                os.remove(self.plot_path)
            output_file(self.plot_path, title=title)
            plot = column(*self.figures)
            save(plot)
            self.figures = []
        self.results.to_csv(self.path, index=False, index_label=False)

    def load(self, path=None):
        path = path or self.path
        if os.path.isfile(path):
            self.results.read_csv(path)

    def show(self):
        if len(self.figures) > 0:
            plot = column(*self.figures)
            show(plot)

    # def plot(self, *kargs, **kwargs):
    #    line = Line(data=self.results, *kargs, **kwargs)
    #    self.figures.append(line)

    def image(self, *kargs, **kwargs):
        fig = figure()
        fig.image(*kargs, **kwargs)
        self.figures.append(fig)


def save_checkpoint(state,
                    is_best, path='.',
                    filename='checkpoint.pth.tar',
                    save_all=False):

    filename = os.path.join(path, filename)
    torch.save(state, filename)
    if is_best:
        shutil.copyfile(filename, os.path.join(path, 'model_best.pth.tar'))
    if save_all:
        shutil.copyfile(filename, os.path.join(
            path, 'checkpoint_epoch_%s.pth.tar' % state['epoch']))


class AverageMeter(object):
    """Computes and stores the average and current value"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


__optimizers = {
    'SGD': torch.optim.SGD,
    'ASGD': torch.optim.ASGD,
    'Adam': torch.optim.Adam,
    'Adamax': torch.optim.Adamax,
    'Adagrad': torch.optim.Adagrad,
    'Adadelta': torch.optim.Adadelta,
    'Rprop': torch.optim.Rprop,
    'RMSprop': torch.optim.RMSprop
}


def adjust_optimizer(optimizer, epoch, config):
    """Reconfigures the optimizer according to epoch and config dict"""
    def modify_optimizer(optimizer, setting):
        if 'optimizer' in setting:
            optimizer = __optimizers[setting['optimizer']](
                optimizer.param_groups)
            logging.debug('OPTIMIZER - setting method = %s' %
                          setting['optimizer'])
        for param_group in optimizer.param_groups:
            for key in param_group.keys():
                if key in setting:
                    logging.debug('OPTIMIZER - setting %s = %s' %
                                  (key, setting[key]))
                    param_group[key] = setting[key]
        return optimizer

    if callable(config):
        optimizer = modify_optimizer(optimizer, config(epoch))
    else:
        for e in range(epoch + 1):  # run over all epochs - sticky setting
            if e in config:
                optimizer = modify_optimizer(optimizer, config[e])

    return optimizer


def accuracy(output, target, topk=(1,)):
    """Computes the precision@k for the specified values of k"""
    maxk = max(topk)
    batch_size = target.size(0)

    _, pred = output.float().topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        correct_k = correct[:k].view(-1).float().sum(0)
        res.append(correct_k.mul_(100.0 / batch_size))
    return res

    # kernel_img = model.features[0][0].kernel.data.clone()
    # kernel_img.add_(-kernel_img.min())
    # kernel_img.mul_(255 / kernel_img.max())
    # save_image(kernel_img, 'kernel%s.jpg' % epoch)

def set_random_seeds(seed=0):
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)

    np.random.seed(seed)
    random.seed(seed)

def get_storing_paths(
                    dataset,
                    split,
                    features,
                    input_dim,
                    initialization,
                    num_layer,
                    num_neuron,
                    lambda_cvx,
                    lambda_mean,
                    optimizer,
                    lr,
                    n_generator_iters,
                    batch_size,
                    trial,
                    full_quadratic,
                    momentum=.5,
                    beta1_adam=.5,
                    beta2_adam=.99,
                    alpha_rmsprop=.99
                    ):
    if full_quadratic:
        full_quadratic_value = "full"
    else:
        full_quadratic_value = "inp"

    if optimizer == 'SGD':
        results_save_path = ('../results/training/{0}/{1}/'
                             '{2}/input_dim_{3}/init_{4}/layers_{5}/neuron_{6}/'
                             'lambda_cvx_{7}_mean_{8}/optim_{9}lr_{10}momen_{15}/'
                             'gen_{11}/batch_{12}/trial_{13}_last_{14}_qudr').format(
                                                                                dataset,
                                                                                split,
                                                                                features,
                                                                                input_dim,
                                                                                initialization,
                                                                                num_layer,
                                                                                num_neuron,
                                                                                lambda_cvx,
                                                                                lambda_mean,
                                                                                optimizer,
                                                                                lr,
                                                                                n_generator_iters,
                                                                                batch_size,
                                                                                trial,
                                                                                momentum,
                                                                                full_quadratic_value,
                                                                                momentum
                                                                                )

    elif optimizer == 'Adam':
        results_save_path = ('../results/training/{0}/{1}/'
                             '{2}/input_dim_{3}/init_{4}/layers_{5}/neuron_{6}/'
                             'lambda_cvx_{7}_mean_{8}/'
                             'optim_{9}lr_{10}betas_{15}_{16}/gen_{11}/batch_{12}/'
                             'trial_{13}_last_{14}_qudr').format(
                                                                dataset,
                                                                split,
                                                                features,
                                                                input_dim,
                                                                initialization,
                                                                num_layer,
                                                                num_neuron,
                                                                lambda_cvx,
                                                                lambda_mean,
                                                                optimizer,
                                                                lr,
                                                                n_generator_iters,
                                                                batch_size,
                                                                trial,
                                                                momentum,
                                                                full_quadratic_value,
                                                                beta1_adam,
                                                                beta2_adam,
                                                                alpha_rmsprop
                                                                )

    elif optimizer == 'RMSProp':
        results_save_path = ('../results/training/{0}/{1}/'
                             '{2}/input_dim_{3}/init_{4}/layers_{5}/neuron_{6}/'
                             'lambda_cvx_{7}_mean_{8}/'
                             'optim_{9}lr_{10}_moment{15}_alpha{16}/gen_{11}/batch_{12}/'
                             'trial_{13}_last_{14}_qudr').format(
                                                                dataset,
                                                                split,
                                                                features,
                                                                input_dim,
                                                                initialization,
                                                                num_layer,
                                                                num_neuron,
                                                                lambda_cvx,
                                                                lambda_mean,
                                                                optimizer,
                                                                lr,
                                                                n_generator_iters,
                                                                batch_size,
                                                                trial,
                                                                momentum,
                                                                full_quadratic_value,
                                                                momentum,
                                                                alpha_rmsprop
                                                                )
    else:
        raise ValueError("The optimizer must be in ['RMSProp', 'SGD', 'Adam']")

    model_save_path = results_save_path + '/storing_models'

    return (results_save_path, model_save_path)

def get_iccns(num_layers=2,
              full_quadratic=False,
              input_dim=512,
              num_neuron=512,
              activation="leaky_relu"):
    if num_layers == 2:

        if full_quadratic:
            convex_f = Simple_Feedforward_2Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_2Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
        else:
            convex_f = Simple_Feedforward_2Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_2Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)

    elif num_layers == 3:

        if full_quadratic:
            convex_f = Simple_Feedforward_3Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_3Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
        else:
            convex_f = Simple_Feedforward_3Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_3Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)

    elif num_layers == 4:

        if full_quadratic:
            convex_f = Simple_Feedforward_4Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_4Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
        else:
            convex_f = Simple_Feedforward_4Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_4Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)

    elif num_layers == 5:

        if full_quadratic:
            convex_f = Simple_Feedforward_5Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_5Layer_ICNN_LastFull_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
        else:
            convex_f = Simple_Feedforward_5Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)
            convex_g = Simple_Feedforward_5Layer_ICNN_LastInp_Quadratic(
                    input_dim,
                    num_neuron,
                    activation)

    return (convex_f, convex_g)

def get_optimizers(f,
                   g,
                   optimizer,
                   lr,
                   momentum=0.5,
                   beta1_adam=0.5,
                   beta2_adam=0.99,
                   alpha_rmsprop=0.99):

    if optimizer == 'SGD':

        optimizer_f = optim.SGD(f.parameters(),
                                lr=lr,
                                momentum=momentum)
        optimizer_g = optim.SGD(g.parameters(),
                                lr=lr,
                                momentum=momentum)

    elif optimizer == 'Adam':

        optimizer_f = optim.Adam(f.parameters(),
                                 lr=lr,
                                 betas=(beta1_adam, beta2_adam),
                                 weight_decay=1e-5)
        optimizer_g = optim.Adam(g.parameters(),
                                 lr=lr,
                                 betas=(beta1_adam, beta2_adam),
                                 weight_decay=1e-5)

    elif optimizer == 'RMSProp':

        optimizer_f = optim.RMSprop(f.parameters(),
                                 lr=lr,
                                 alpha=alpha_rmsprop,
                                 momentum=momentum)
        optimizer_g = optim.RMSprop(g.parameters(),
                                 lr=lr,
                                 alpha=alpha_rmsprop,
                                 momentum=momentum)

    else:
        raise ValueError("optimizer not in ['Adam', 'RMSProp', 'SGD']")

    return (optimizer_f, optimizer_g)