import numpy as np
import matplotlib.pyplot as plt

# Example data: chaos heatmap (like before)
chaos_data = np.random.rand(10, 10)

# Example wind vector field (u and v components)
X, Y = np.meshgrid(np.arange(0, 10, 1), np.arange(0, 10, 1))
U = np.random.randn(10, 10)  # Wind component in X direction
V = np.random.randn(10, 10)  # Wind component in Y direction

# Plot the heatmap
plt.imshow(chaos_data, cmap='inferno', interpolation='nearest')
plt.colorbar(label='Chaos Level')

# Overlay the streamplot (wind direction and flow)
plt.streamplot(X, Y, U, V, color='white', linewidth=1, density=1.5)

plt.title('Ocean Chaos with Wind Streamlines')
plt.xlabel('Longitude / X-axis (Spatial or Time)')
plt.ylabel('Latitude / Y-axis (Spatial or Metric)')

plt.show()
