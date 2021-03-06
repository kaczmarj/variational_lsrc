import os
import numpy as np
from argparse import ArgumentParser
from nipype import Function, Node, Workflow, IdentityInterface

parser = ArgumentParser(prog="run_sing.py", description=__doc__)
parser.add_argument("-bp", "--bind_path", type=str, help="bind path for image")
parser.add_argument("-ip", "--img_path", type=str, help="path to the singularity image")
parser.add_argument("-nr", "--nruns", type=str, help="number of instances to spin up")
parser.add_argument("-dp", "--data_path", type=str, help="where data is")
parser.add_argument("-sn", "--save_name", type=str, help="name of results file")
parser.add_argument("-cn", "--cnames", type=str, help="column string dataset in h5 file")
args = parser.parse_args()

try:
    nruns = int(args.nruns)
except:
    raise Exception("number of runs should be an integer")

if not os.path.isdir(args.save_name):
    os.makedirs(args.save_name)

cwd = os.getcwd()
wf = Workflow(name="sing")
wf.base_dir = cwd

Iternode = Node(IdentityInterface(fields=["run_idx"]), name="Iternode")
Iternode.iterables = ("run_idx", np.arange(nruns)+1)

def write_varbvs(base_dir, data_path, save_name, col_idx, cnames):
    import os
    f_name = "bf-feature_idx-{}.csv".format(col_idx)
    shfile = "\n".join([
        "#!/bin/bash", ("R_DEFAULT_PACKAGES= Rscript "
        "{script} {data_path} {save_name} {col_idx} {cnames}")
    ])
    file_name = os.path.join(base_dir, "gtoi_template.r")
    r_file = shfile.format(
        script=file_name, data_path=data_path,
        save_name=save_name, col_idx=col_idx, cnames=cnames
    )
    if os.getcwd() != base_dir:
        os.chdir(base_dir)
    wd = f_name.split(".")[0]
    os.makedirs(wd)
    os.chdir(wd)
    rf = "r_file_{}.sh".format(wd)
    with open(rf, 'w') as f:
        f.write(r_file)
    script_path = os.path.join(os.getcwd(), rf)
    return script_path, col_idx, save_name

def run_sing(bind_path, img_path, base_dir, run_idx, script_path):
    import os
    from subprocess import call
    singfile = "\n".join([
        "#!/bin/bash", "#SBATCH --mem=6G", "#SBATCH -c 2",
        "#SBATCH --time=02:00:00", ("singularity exec --bind "
        "{bind_path} {img_path} {cmd}")
    ])
    path_to_cd = "/".join(script_path.split("/")[:-1])
    if os.getcwd() != path_to_cd:
        os.chdir(path_to_cd)
    singfile = singfile.format(bind_path=bind_path, img_path=img_path,
                               cmd="bash {}".format(script_path))
    sif = os.path.join(path_to_cd, "sbatch_file-{}.sh".format(run_idx))
    with open(sif, 'w') as f:
        f.write(singfile)
    call("sbatch {}".format(sif).split())
    return None

# something is wrong here, or in the way it was saved
# also this should probably be called in another script
#def check_failed(save_name, data_path, cnames):
#    import os
#    import numpy as np
#    import pandas as pd
#    import h5py
#    snfiles = [x.split('-') for x in os.listdir(save_name)]
#    df = pd.DataFrame()
#    df["col_idx"] = [int(i[1]) for i in snfiles]
#    df["col_name"] = [i[2] for i in snfiles]
#    df = df.sort_values("col_idx").reset_index(drop=True)
#    df = df.set_index("col_idx")
#    missing = np.setdiff1d(np.arange(170)+1, df["col_idx"].values)
#    with open(data_path, 'r') as h5f:
#        icols = h5f.get(cnames).value
#    dfm = pd.DataFrame()
#    dfm["col_val"] = [str(i, 'utf-8') for i in icols]
#    dfm["col_idx"] = np.arange(170)+1
#    dfm = dfm.set_index("col_idx")
#    result = dfm.iloc[missing]


Write_Varbvs = Node(interface=Function(
        input_names=["base_dir", "data_path", "save_name", "col_idx", "cnames"],
        output_names=["script_path", "col_idx", "save_name"],
        function=write_varbvs
    ),
    name="Write_Varbvs"
)

Run_Sing = Node(interface=Function(
        input_names=["bind_path", "img_path", "base_dir", "run_idx", "script_path"],
        output_names=[],
        function=run_sing,
    ),
    name="Run_Sing",
)

Write_Varbvs.inputs.base_dir = wf.base_dir
Write_Varbvs.inputs.data_path = args.data_path
Write_Varbvs.inputs.save_name = args.save_name
Write_Varbvs.inputs.cnames = args.cnames
wf.connect(Iternode, "run_idx", Write_Varbvs, "col_idx")
Run_Sing.inputs.bind_path = args.bind_path
Run_Sing.inputs.img_path = args.img_path
Run_Sing.inputs.base_dir = wf.base_dir
wf.connect(Write_Varbvs, "col_idx", Run_Sing, "run_idx")
wf.connect(Write_Varbvs, "script_path", Run_Sing, "script_path")
wf.run()
