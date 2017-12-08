import pandas as pd;
import entropy_estimators as ee;
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.pyplot as plt
from matplotlib import cm

meta_data = pd.read_csv("studies.csv");
result = dict();
fig = plt.figure()

for i in range(len(meta_data)):
    before = pd.read_csv("synapse-data/"+meta_data['Before'][i]);
    after = pd.read_csv("synapse-data/"+meta_data['After'][i]);
    
    before_x = before["X"].values;
    before_y = before["Y"].values;
    before_z = before["Z"].values;
    before_c = before["raw core"].values;

    after_x = after["X"].values;
    after_y = after["Y"].values;
    after_z = after["Z"].values;
    after_c = after["raw core"].values;

    before_xyz = [];
    before_xyzc = [];
    for j in range(len(before_x)):
        before_xyz.append([before_x[j], before_y[j], before_z[j]]);
        before_xyzc.append([before_x[j], before_y[j], before_z[j], before_c[j]]);

    after_xyz = [];
    after_xyzc = [];
    for j in range(len(after_x)):
        after_xyz.append([after_x[j], after_y[j], after_z[j]]);
        after_xyzc.append([after_x[j], after_y[j], after_z[j], after_c[j]]);
        
    kl_xyz, pw_xyz = ee.kldiv(before_xyz, after_xyz, return_pw = True)
    
    plt.clf();
    ax = fig.add_subplot(111, projection='3d');
    cs = ax.scatter(before_x, before_y, before_z, c=pw_xyz, cmap=cm.jet);
    plt.title("StudyID:"+meta_data["Study"][i]+"\nType:"+meta_data['Type'][i] + "\nKL divergence= "+("%.3f" % kl_xyz));
    plt.colorbar(cs);
    plt.savefig("figs/"+meta_data['Type'][i]+"_"+meta_data["Study"][i]+".jpg", bbox_inches='tight');
   
    f_out = open("pointwise_kl/"+meta_data['Type'][i]+"_"+meta_data["Study"][i]+".csv", 'w');
    f_out.write("X,Y,Z,pointwise_kl_divergence\n");
    for i in range(len(before_xyz)):
        f_out.write(str(before_xyz[i][0]) + "," + str(before_xyz[i][1]) + "," + str(before_xyz[i][2]) + "," + str(pw_xyz[i]) + "\n");
        
    
