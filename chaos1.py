import numpy as np
import matplotlib.pyplot as plt

# Example data: a 10x10 grid for chaos (heatmap)
chaos_data = np.random.rand(10, 10)

# Example data: wind direction (u and v components of wind vector)
X, Y = np.meshgrid(np.arange(0, 10, 1), np.arange(0, 10, 1))  # Grid of positions
U = np.random.randn(10, 10)  # Wind component in X direction
V = np.random.randn(10, 10)  # Wind component in Y direction

# Plot the heatmap
plt.imshow(chaos_data, cmap='inferno', interpolation='nearest')
plt.colorbar(label='Chaos Level')

# Overlay the quiver plot (wind direction and speed)
plt.quiver(X, Y, U, V, color='white')  # Quiver plot (arrows)

plt.title('Ocean Chaos with Wind Direction')
plt.xlabel('Longitude / X-axis (Spatial or Time)')
plt.ylabel('Latitude / Y-axis (Spatial or Metric)')

plt.show()
