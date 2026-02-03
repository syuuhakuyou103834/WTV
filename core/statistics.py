import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

def calculate_histogram(thickness, bin_size=None):
    if not bin_size:
        iqr = np.percentile(thickness, 75) - np.percentile(thickness, 25)
        bin_size = 2 * iqr / (len(thickness) ** (1/3))
        bin_size = max(bin_size, (thickness.max()-thickness.min())/20)
        bin_size = round(bin_size, 2)
    
    bins = np.arange(thickness.min(), thickness.max() + bin_size, bin_size)
    n, bins = np.histogram(thickness, bins=bins, density=True)
    
    cumulative = np.cumsum(n) * bin_size
    return n, bins, cumulative, bin_size

def generate_statistics_plot(thickness, bin_size=None):
    mu = np.mean(thickness)
    sigma = np.std(thickness)
    
    # Create plot
    fig = Figure(figsize=(8, 6))
    canvas = FigureCanvasAgg(fig)
    
    # Add histogram subplot
    ax1 = fig.add_subplot(211)
    n, bins, cumulative, bin_size = calculate_histogram(thickness, bin_size)
    ax1.hist(thickness, bins=bins, density=True, alpha=0.7, edgecolor='black')
    ax1.set_title(f"厚度分布直方图（组距：{bin_size:.2f}nm）")
    ax1.set_xlabel("厚度 (nm)")
    ax1.set_ylabel("频率密度")
    ax1.grid(True, alpha=0.3)
    
    # Add cumulative plot
    ax2 = ax1.twinx()
    ax2.plot(bins[:-1], cumulative, 'darkorange', linestyle='--', linewidth=2)
    ax2.set_ylabel('累积概率', rotation=270, labelpad=20)
    
    # Add normal distribution subplot
    ax3 = fig.add_subplot(212)
    xmin, xmax = thickness.min()-3*sigma, thickness.max()+3*sigma
    x = np.linspace(xmin, xmax, 300)
    pdf = (1/(sigma * np.sqrt(2*np.pi))) * np.exp(-0.5*((x-mu)/sigma)**2)
    ax3.plot(x, pdf, 'r-', linewidth=2)
    ax3.fill_between(x, pdf, 0, alpha=0.3, color='red')
    ax3.set_title("正态分布拟合曲线")
    ax3.set_xlabel("厚度 (nm)")
    ax3.set_ylabel("概率密度")
    ax3.grid(True, alpha=0.3)
    
    # Add statistics text
    textstr = '\n'.join((
        fr'$\mu=%.2f$ nm' % mu,
        fr'$\sigma=%.2f$ nm' % sigma,
        fr'$\sigma^2=%.2f$ nm²' % (sigma**2)
    ))
    props = dict(boxstyle='round', facecolor='white', alpha=0.8)
    ax3.text(0.98, 0.95, textstr, transform=ax3.transAxes, verticalalignment='top', 
             horizontalalignment='right', bbox=props)
    
    fig.tight_layout()
    return fig, bin_size
