# gpsmax/visualize/plot.py
"""
Plotting routines for GPSmax
"""

import matplotlib.pyplot as plt

def plot_speed(points, speeds):
    lats = [p.lat for p in points[:-1]]
    lons = [p.lon for p in points[:-1]]

    plt.figure(figsize=(8,6))
    sc = plt.scatter(lons, lats, c=speeds, s=5, cmap="viridis")
    plt.colorbar(sc, label="Speed (m/s)")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.title("Track coloured by speed")
    plt.show()
