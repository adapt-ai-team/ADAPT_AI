import gradio as gr
import requests

def process_input(image, location):
    response = requests.post("http://127.0.0.1:5000/process", json={"image": image, "location": location})
    return response.json()["output_image"]

gr.Interface(
    fn=process_input,
    inputs=["image", "text"],
    outputs="image",
    title="3D Model Generation & Analysis"
).launch()
