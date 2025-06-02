Your own private server for Microsoft's Trellis, to generate 3D geometry.
You need an Nvidia GPU with 8GB+ of VRAM, which supports float16 (half-precision).

Uses flexicubes fork  https://github.com/IgorAherne/flexicubes-stable-projectorz
I've changed it to use int32 instead of int64, reducing memory by half during SLAT decoding stage.
I've added support for float16 instead of float32 within the pipeline, to fit into the VRAM.


To launch, double-click either:


	run-fp16.bat  to run in half-precision mode (increased speed and compactness, with a tiny drop in quality)


	run.bat  to run in full-precision mode (your gpu has to be at least 12-16 GB vram, else might give Out-of-Memory errors)
	
	
	run-gradio-fp16.bat  to run in browser in half-precision mode (great for GPUs with 8GB memory)
	
	
	run-gradio.bat  to run in browser.
	
 
	update.bat  to fetch most recent version of code.


I added API capabilities. You can communicate with the server:
pinging, requesting generation (with/without video previews), downloading videos, downloading gbl geometry, cancelling.
This is how  StableProjectorz  communicates with the server.

For a full list of such endpoints,  see api_spz/api-documentation.html 
For actual code, you can inspect  api_spz/generate.py


You can pass arguments to run.bat  such as --ip, --port, --precision  with appropriate values.
Right click and edit run.bat  to  see which arguments can be used.
Or inspect  api_spz/main_api.py  for a full list of server arguments.



Let's make some awesome stuff



Thank you to every contributor:
https://github.com/IgorAherne/trellis-stable-projectorz

https://stableprojectorz.com
https://discord.gg/aWbnX2qan2
Igor Aherne 2025