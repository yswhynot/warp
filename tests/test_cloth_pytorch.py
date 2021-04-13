import torch

print(torch.__version__)

import torch_scatter



def eval_springs(x,
                 v,
                 indices,
                 rest,
                 ke,
                 kd,
                 f):

    i = indices[:,0]
    j = indices[:,1]

    xi = x[i]
    xj = x[j]

    vi = v[i]
    vj = v[j]

    xij = xi - xj
    vij = vi - vj

    l = torch.linalg.norm(xij, axis=1)
    l_inv = 1.0 / l

    # normalized spring direction
    dir = (xij.T * l_inv).T

    c = l - rest
    dcdt = torch.sum(dir*vij, axis=1)

    # damping based on relative velocity.
    fs = dir.T*(ke * c + kd * dcdt)

    #torch.scatter_add(f, i, -fs.T)
    #torch.scatter_add(f, j,  fs.T)
    #edges[:,0]
    torch_scatter.scatter_add(out=f, src=-fs.T, index=i, dim=0, dim_size=3)
    torch_scatter.scatter_add(out=f, src=fs.T, index=j, dim=0, dim_size=3)



def integrate_particles(x,
                        v,
                        f,
                        g,
                        w,
                        dt):

    s = w > 0.0

    a_ext = g*s[:,None]

    # simple semi-implicit Euler. v1 = v0 + a dt, x1 = x0 + v1 dt
    v += ((f.T * w).T + a_ext) * dt
    x += (v * dt)

    # clear forces
    f *= 0.0


class TrIntegrator:

    def __init__(self, cloth, device):

        self.cloth = cloth

        self.positions = torch.tensor(self.cloth.positions, device=device)
        self.velocities = torch.tensor(self.cloth.velocities, device=device)
        self.inv_mass = torch.tensor(self.cloth.inv_masses, device=device)

        self.spring_indices = torch.tensor(self.cloth.spring_indices, device=device, dtype=torch.long)
        self.spring_lengths = torch.tensor(self.cloth.spring_lengths, device=device)
        self.spring_stiffness = torch.tensor(self.cloth.spring_stiffness, device=device)
        self.spring_damping = torch.tensor(self.cloth.spring_damping, device=device)
        
        self.forces = torch.zeros((self.cloth.num_particles, 3), dtype=torch.float32, device=device)
        self.gravity = g = torch.tensor((0.0, 0.0 - 9.8, 0.0), dtype=torch.float32, device=device)


    def simulate(self, dt, substeps):

        sim_dt = dt/substeps
        
        for s in range(substeps):

            eval_springs(self.positions, 
                        self.velocities,
                        self.spring_indices.reshape((self.cloth.num_springs, 2)),
                        self.spring_lengths,
                        self.spring_stiffness,
                        self.spring_damping,
                        self.forces)

            # integrate 
            integrate_particles(
                self.positions,
                self.velocities,
                self.forces,
                self.gravity,
                self.inv_mass,
                sim_dt)

        return self.positions.cpu().numpy()