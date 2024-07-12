import rainflow
import numpy as np
data = np.genfromtxt("./TimeSeries.txt",dtype=[float,float])
StressRange = [x[1] for x in data]
print(StressRange)
countCycles = rainflow.count_cycles(StressRange, binsize=1e4) #假定0.01MPa间隔

for x in countCycles:
    print(x)


