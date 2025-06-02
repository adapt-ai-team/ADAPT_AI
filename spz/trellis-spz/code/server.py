from flask import Flask, request, jsonify
import os
import sys

# Add the Trellis module path
sys.path.append(os.getcwd())  # Add current working directory
sys.path.append(r"D:\spz\trellis-spz")  # Add Trellis directory path

# Set environment variables for Trellis
os.environ['ATTN_BACKEND'] = 'xformers'
os.environ['SPCONV_ALGO'] = 'native'

from PIL import Image
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import render_utils, postprocessing_utils
import imageio

app = Flask(__name__)

@app.route('/process-image', methods=['POST'])
def process_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    # Get the uploaded file
    file = request.files['image']
    
    # Load the pipeline
    pipeline = TrellisImageTo3DPipeline.from_pretrained("JeffreyXiang/TRELLIS-image-large")
    pipeline.cuda()

    # Process the uploaded image
    image = Image.open(file)
    
    # Run the pipeline
    outputs = pipeline.run(
        image,
        seed=1
    )

    # Generate GLB file
    glb = postprocessing_utils.to_glb(
        outputs['gaussian'][0],
        outputs['mesh'][0],
        simplify=0.95,
        texture_size=1024,
    )
    glb.export(r"D:\spz_pipeline\pipeline_outputs\example_image.glb")

    return jsonify({'status': 'success', 'message': 'Image processed successfully'})

if __name__ == '__main__':
    app.run(port=5000)