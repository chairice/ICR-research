from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np
import scipy as sp
from pathlib import Path
import swiftbat

#setup
mspattern ="bat/rate/sw*brtms.lc.gz"
pathname = Path("/opt/data/mirror/swift")
obsid="00059158012"

filename = list(pathname.joinpath(obsid).glob(mspattern))[0]
data, header = fits.getdata(filename,  header=True)
tb = np.median(np.diff(data['TIME']))    # size of the timebin (ignoring jumps)

# splitting the data by time gaps
splitlocs = np.argwhere(np.diff(data['TIME']) > 1.5*tb).ravel() + 1 # gives index of the next time block

# print out all the time gaps and the durations
for datasegment in np.split(data, splitlocs):
    # time of spacecraft, not always accurate because of clock error
    starttime = swiftbat.met2datetime(datasegment['TIME'][0])
    duration = datasegment['TIME'].ptp()
    print(f"{starttime:%Y-%m-%dT%H:%M:%S} + {duration:5.10f} seconds to the end of the block")
    if duration > 1300:
        longdatasegment = datasegment      


# get the highest number of datapoints for FFT
def prev_fast_FFT_len(n):
    ntry = n
    nfft = sp.fft.next_fast_len(ntry)
    while nfft > n and ntry > 1:
        ntry = int(ntry * 0.99) - 1
        nfft = sp.fft.next_fast_len(ntry)
    return nfft

# refind the amount of datapoints afte cutting off the first minute (BAT is still adjusting the first min)
n = prev_fast_FFT_len(len(longdatasegment) - int(60 / tb))

# Trim to the last n values
datasegment = longdatasegment[-n:]
duration = datasegment['TIME'].ptp()
print(f"{duration:.3f} seconds after trimming")

# Rate for the segment
rate = np.sum(datasegment['COUNTS'][:,0:2], axis=-1)/tb
'''
fig,ax = plt.subplots(nrows = 1, ncols = 1)
ax.plot(np.arange(len(rate)) * tb, rate)
ax.set(xlabel='Time??', ylabel='Rate (counts/sec)')
fig.tight_layout()
'''

# ABOUT FOURIER TRANSFORM
# Forward (time series->frequency) FFT for real input
# Subtract the mean to avoid a huge term at 0 frequency

# subtracting the mean makes it easier to see variations instead of just average
frate = sp.fft.rfft(rate - np.mean(rate), norm = "forward")
# print(frate[10:20])
# not transformed, used as reference for interpreting FFTs
freqs = sp.fft.rfftfreq(len(rate), tb)
# print(freqs[10:20])
for i in range(10,20):
    print(frate[i],freqs[i])

fig,ax = plt.subplots(1,1)
ax.plot(freqs, np.abs(frate))
ax.set(xlabel="Frequency (Hz)", ylabel="Amplitude")
ax.set_title("Fourier Transform of Longest Data Segment")
fig.tight_layout()

# Forward (time series->frequency) FFT for real input
# Subtract the mean to avoid a huge term at 0 frequency
frate = sp.fft.rfft(rate, norm = "forward")
# print(frate[10:20])
freqs = sp.fft.rfftfreq(len(rate), tb)
# print(freqs[10:20])

invrate = sp.fft.irfft(frate, norm = "forward")
#for i in range(10,20):
#    print(frate[i],freqs[i])
times = np.arange(len(rate)) * tb

estrate = np.zeros(len(rate))
# component amplitude * 2 is generally how far away from the curve the data points are
ncomponents = 10
# sort from lowest to highest and then flip array
ibest = np.argsort(np.abs(frate))[::-1]
# count of cycles in entire observation


# Plot out FFT and inverse of data
fig,(axf,axr) = plt.subplots(nrows = 2, ncols = 1)
axf.plot(freqs, np.abs(frate))
axf.set(xlabel="Frequency (Hz)", ylabel="Amplitude")
axr.plot(times, rate, ".")
for i in ibest[:ncomponents]:
    print(f"{i:8d} {freqs[i]:8.4f} {np.abs(frate[i])} {np.rad2deg(np.angle(frate[i]))}")
    estrate += (1 if i == 0 else 2) * np.real(frate[i] * np.exp(times * freqs[i] * 1j * 2 * np.pi))
    # phase: angle of the spin of the star as of the start of the datasegment (only at correct frequency)
    axr.plot(times, estrate)
axr.set(xlabel="Seconds", ylabel="Rate", xlim = [0,20])
axf.set_title(f"FFT and inverse of {ncomponents} datapoints")
fig.tight_layout()


# adjusting work
tzero = swiftbat.string2met('2017-11-01T00:00:00')
print(tzero)
fapprox = 0.1018-.45/5761.79200006
# cycle of seconds since tzero, spin angle of a specific point
cycle, phase = np.divmod((datasegment['TIME']-tzero) * fapprox, 1)

fig, axes = plt.subplots(nrows = 2, ncols = 1, sharex = True)

# plotting just the 1300s segment
rate = np.sum(datasegment['COUNTS'][:,0:2], axis=-1)/tb
print(len(phase), len(rate))
print(len(datasegment))

segpieces = 4
# Break the segment into 4 pieces
pointsperplot = 2 * int(1/(0.064 * fapprox))
# For each segment, plot 2 cycles of data
for istart in np.arange(0, len(datasegment), 1 + len(datasegment)//segpieces):
    sl = slice(istart, istart+pointsperplot)
    axes[0].plot(phase[sl], rate[sl], ".", label=f"{datasegment[sl.start]['time'] - tzero:.0f}") 
axes[0].legend()
axes[0].set_title(f"For Longest Segment: Change in Rate Over a Phase with Freq of {fapprox} Hz")

# 1 cycle of data for all 11 data segments
for datasegment in np.split(data, splitlocs):
    n = prev_fast_FFT_len(len(datasegment) - int(60 / tb))
    datasegment = datasegment[-n:]
    duration = datasegment['TIME'].ptp()
    print("time: ", datasegment['TIME'][0])
    print(f"{duration:.3f} seconds after trimming")
    segrate = np.sum(datasegment['COUNTS'][:,0:2], axis=-1)/tb
    segcycle, segphase = np.divmod((datasegment['TIME']-tzero) * fapprox, 1)
    print(len(datasegment))
    axes[1].plot(segphase[0:3675], segrate[0:3675], ".")
    
axes[1].legend()
axes[1].set_title(f"For All 11 segments: Change in Rate Over a Phase with Freq of {fapprox} Hz")
    
fig.tight_layout()

plt.show()


# adjusting work
tzero = swiftbat.string2met('2017-11-01T00:00:00')
print(tzero)
fapprox = 0.1018-.45/5761.79200006
# cycle of seconds since tzero, spin angle of a specific point
cycle, phase = np.divmod((datasegment['TIME']-tzero) * fapprox, 1)

fig, axes = plt.subplots(nrows = 11, ncols = 1, sharex = True)

# plotting just the 1300s segment
rate = np.sum(datasegment['COUNTS'][:,0:2], axis=-1)/tb
print(len(phase), len(rate))
print(len(datasegment))

segpieces = 4
# Break the segment into 4 pieces
pointsperplot = 2 * int(1/(0.064 * fapprox))
# For each segment, plot 2 cycles of data

# 2 cycles of data for all 11 data segments
for datasegment, ax in zip(np.split(data, splitlocs), axes):
    n = prev_fast_FFT_len(len(datasegment) - int(60 / tb))
    datasegment = datasegment[-n:]
    duration = datasegment['TIME'].ptp()
    segrate = np.sum(datasegment['COUNTS'][:,0:2], axis=-1)/tb
    segcycle, segphase = np.divmod((datasegment['TIME']-tzero) * fapprox, 1)
    ax.plot(segphase[0:3675], segrate[0:3675], ".")
    
fig.tight_layout()

plt.show()
