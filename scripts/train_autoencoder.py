import random
import torch.nn as nn
import torch.nn.parallel
import torch.optim as optim
import torch.utils.data
import torchvision.datasets as dset
import torch
from torch.autograd import Variable
import torchvision
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from datetime import datetime

#we set random seed for reproducibility
manualSeed = 999
#manualSeed = random.randint(1, 10000)
print("Random Seed: ", manualSeed)
random.seed(manualSeed)
torch.manual_seed(manualSeed)

dataroot = "../data/celeba/Neuer Ordner"
full_data = dset.ImageFolder(root=dataroot,
                           transform=transforms.Compose([
                               transforms.Resize(128),
                               transforms.CenterCrop(128),
                               transforms.ToTensor(),
                               transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
                           ]))

train_size = int(0.1 * len(full_data))
test_size = len(full_data) - train_size
train_dataset, test = torch.utils.data.random_split(full_data, [train_size, test_size])
test1_size=int(0.01*len(test))
test2_size=len(test)-test1_size
test_dataset,test_=torch.utils.data.random_split(test,[test1_size,test2_size])

dataloader = DataLoader(train_dataset, batch_size=128, shuffle=True)
dataloader_t=DataLoader(test_dataset, batch_size=128, shuffle=True)
class AE(nn.Module):
    def __init__(self, nc, ngf, ndf, latent_variable_size):
        super(AE, self).__init__()

        self.nc = nc
        self.ngf = ngf
        self.ndf = ndf
        self.latent_variable_size = latent_variable_size

        # encoder
        self.e1 = nn.Conv2d(nc, ndf, 4, 2, 1)
        self.bn1 = nn.BatchNorm2d(ndf)

        self.e2 = nn.Conv2d(ndf, ndf*2, 4, 2, 1)
        self.bn2 = nn.BatchNorm2d(ndf*2)

        self.e3 = nn.Conv2d(ndf*2, ndf*4, 4, 2, 1)
        self.bn3 = nn.BatchNorm2d(ndf*4)

        self.e4 = nn.Conv2d(ndf*4, ndf*8, 4, 2, 1)
        self.bn4 = nn.BatchNorm2d(ndf*8)

        self.e5 = nn.Conv2d(ndf*8, ndf*8, 4, 2, 1)
        self.bn5 = nn.BatchNorm2d(ndf*8)

        self.fc1 = nn.Linear(ndf*8*4*4, latent_variable_size)
        self.fc2 = nn.Linear(ndf*8*4*4, latent_variable_size)

        # decoder
        self.d1 = nn.Linear(latent_variable_size, ngf*8*2*4*4)

        self.up1 = nn.UpsamplingNearest2d(scale_factor=2)
        self.pd1 = nn.ReplicationPad2d(1)
        self.d2 = nn.Conv2d(ngf*8*2, ngf*8, 3, 1)
        self.bn6 = nn.BatchNorm2d(ngf*8, 1.e-3)

        self.up2 = nn.UpsamplingNearest2d(scale_factor=2)
        self.pd2 = nn.ReplicationPad2d(1)
        self.d3 = nn.Conv2d(ngf*8, ngf*4, 3, 1)
        self.bn7 = nn.BatchNorm2d(ngf*4, 1.e-3)

        self.up3 = nn.UpsamplingNearest2d(scale_factor=2)
        self.pd3 = nn.ReplicationPad2d(1)
        self.d4 = nn.Conv2d(ngf*4, ngf*2, 3, 1)
        self.bn8 = nn.BatchNorm2d(ngf*2, 1.e-3)

        self.up4 = nn.UpsamplingNearest2d(scale_factor=2)
        self.pd4 = nn.ReplicationPad2d(1)
        self.d5 = nn.Conv2d(ngf*2, ngf, 3, 1)
        self.bn9 = nn.BatchNorm2d(ngf, 1.e-3)

        self.up5 = nn.UpsamplingNearest2d(scale_factor=2)
        self.pd5 = nn.ReplicationPad2d(1)
        self.d6 = nn.Conv2d(ngf, nc, 3, 1)

        self.leakyrelu = nn.LeakyReLU(0.2)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()

    def encode(self, x):
        h1 = self.leakyrelu(self.bn1(self.e1(x)))
        h2 = self.leakyrelu(self.bn2(self.e2(h1)))
        h3 = self.leakyrelu(self.bn3(self.e3(h2)))
        h4 = self.leakyrelu(self.bn4(self.e4(h3)))
        h5 = self.leakyrelu(self.bn5(self.e5(h4)))
        h5 = h5.view(-1, self.ndf*8*4*4)


        return self.fc1(h5)



    def decode(self, z):
        h1 = self.relu(self.d1(z))
        h1 = h1.view(-1, self.ngf * 8 * 2, 4, 4)
        h2 = self.leakyrelu(self.bn6(self.d2(self.pd1(self.up1(h1)))))
        h3 = self.leakyrelu(self.bn7(self.d3(self.pd2(self.up2(h2)))))
        h4 = self.leakyrelu(self.bn8(self.d4(self.pd3(self.up3(h3)))))
        h5 = self.leakyrelu(self.bn9(self.d5(self.pd4(self.up4(h4)))))

        return self.sigmoid(self.d6(self.pd5(self.up5(h5))))



    def forward(self, x):
        mu = self.encode(x.view(-1, self.nc, self.ndf, self.ngf))
       
        res = self.decode(mu)
        return res


model = AE(nc=3, ngf=128, ndf=128, latent_variable_size=512)



reconstruction_function = nn.BCELoss()
reconstruction_function.size_average = False
def loss_function(recon_x, x):
    BCE = reconstruction_function(recon_x, x)

 

    return BCE 

optimizer = optim.Adam(model.parameters(), lr=1e-4)


def train(epoch):
    model.train()
    train_loss = 0
    for data in dataloader:

        #print(data)
        data = Variable(data[0])
        #print(data.shape)

        optimizer.zero_grad()
        recon_batch = model(data)
        loss = loss_function(recon_batch, data)
        loss.backward()
        train_loss += loss.item()
        optimizer.step()
        

    print('====> Epoch: {} Average loss: {:.4f}'.format(
          epoch, 10*128*train_loss / len(train_dataset)))
    return 10*128*train_loss / len(train_dataset)

def test(epoch):
    model.eval()
    test_loss = 0
    for data in dataloader_t:

        # print(data)
        data = Variable(data[0])

        recon_batch = model(data)
        test_loss += loss_function(recon_batch, data).item()

    torchvision.utils.save_image(data.data, '../imgs/Epoch_{}_data.jpg'.format(epoch), nrow=8, padding=2)
    torchvision.utils.save_image(recon_batch.data, '../imgs/Epoch_{}_recon.jpg'.format(epoch), nrow=8, padding=2)

    test_loss = 10*128*test_loss/len(test_dataset)
    print('====> Test set loss: {:.4f}'.format(test_loss))
    torch.save(model.state_dict(), '../imgs/autoencoder_{}.pth'.format(epoch))

    return test_loss

for epoch in range(20):
    t = datetime.now()
    print(t)
    train(epoch)
    test(epoch)

'''model.load_state_dict(torch.load('../imgs/autoencoder_19.pth'))
#print(full_data[1][0].shape)
for i in range(len(full_data)):
    embedding=model.encode(full_data[i][0].reshape(1,3,128,128))
    torch.save(embedding,'../imgs/encoder_extraction/{}.pt'.format(str(i+1).zfill(6)))'''