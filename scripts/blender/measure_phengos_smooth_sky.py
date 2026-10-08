"""Measure cloud roughness and one-time filter-cache fidelity on proof PNGs."""
import json
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path('E:/LifeOS-Art/phengos')
def read(name):
    return np.asarray(Image.open(OUT/name).convert('RGB'), dtype=np.float64)/255

# Left cloud bank away from the circle: robust high-pass variation limits the
# influence of independently sharp stars. This isn't a subjective style score.
def roughness(image):
    blue = image[250:850,100:648,2].reshape(150,4,137,4).mean(axis=(1,3))
    lap = np.abs(4*blue[1:-1,1:-1]-blue[:-2,1:-1]-blue[2:,1:-1]
                 -blue[1:-1,:-2]-blue[1:-1,2:])
    return float(np.mean(np.minimum(lap, np.quantile(lap, 0.95))))

old = read('reference-v16-idle.png')
new = read('smooth-sky-v17-idle.png')
source_roughness, new_roughness = roughness(old), roughness(new)
result = {'cloud_crop_xywh':[100,250,548,600],
          'v16_robust_laplacian':source_roughness,
          'v17_robust_laplacian':new_roughness,
          'high_frequency_reduction':1-new_roughness/source_roughness,
          'cache_fidelity':{}}
for label in ('opening', 'idle'):
    a = read('smooth-sky-v17-dense-'+label+'.png')
    b = read('smooth-sky-v17-'+label+'.png')
    delta = np.abs(a-b)
    result['cache_fidelity'][label] = {'mean_rgb_error':float(delta.mean()),
        'p99_rgb_error':float(np.quantile(delta,0.99)), 'max_rgb_error':float(delta.max())}
print(json.dumps(result, indent=2))
assert result['high_frequency_reduction'] > 0.3
assert all(v['mean_rgb_error'] < 0.003 for v in result['cache_fidelity'].values())
(OUT/'smooth-sky-v17-image-qa.json').write_text(json.dumps(result, indent=2))
