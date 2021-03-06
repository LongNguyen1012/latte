from flask import Flask, render_template, request, jsonify
from models import BoundingBox
from pointcloud import PointCloud
from predict_label import predict_label
from mask_rcnn import get_mask_rcnn_labels
from frame_handler import FrameHandler
from bounding_box_predictor import BoundingBoxPredictor
import numpy as np
import json
import os
from pathlib import Path
import zipfile
import shutil

app = Flask(__name__, static_url_path='/static')
app.config["UPLOAD_FOLDER"] = "./test_dataset"
DIR_PATH = os.path.dirname(os.path.realpath(__file__))

fh = None
bp = None

@app.route("/")
def root():
	return render_template("index.html")


@app.route('/upload-image', methods = ['POST'])
def upload_file():
	f = request.files['image_file']
	file_path = "./app/zip_dataset/{}".format(f.filename)
	f.save(file_path)

	output_path = "./app/unzip_dataset/{}".format(f.filename.replace(".zip", ""))
	with zipfile.ZipFile(file_path, 'r') as zip_ref:
		zip_ref.extractall(output_path)

	file_name = f.filename.replace(".zip", "")
	source = "./app/unzip_dataset/{}/{}".format(file_name, file_name)
	destination = "./app/test_dataset/{}".format(file_name, file_name)
	dest = shutil.move(source, destination) 

	global fh
	global bp
	fh = FrameHandler()
	bp = BoundingBoxPredictor(fh)

	return 'file uploaded successfully'


@app.route("/initTracker", methods=["POST"])
def init_tracker():
	json_request = request.get_json()
	pointcloud = PointCloud.parse_json(json_request["pointcloud"])
	tracker = Tracker(pointcloud)
	return "success"


@app.route("/trackBoundingBoxes", methods=['POST'])
def trackBoundingBox():
	json_request = request.get_json()
	pointcloud = PointCloud.parse_json(json_request["pointcloud"], json_request["intensities"])
	filtered_indices = tracker.filter_pointcloud(pointcloud)
	next_bounding_boxes = tracker.predict_bounding_boxes(pointcloud)
	print(next_bounding_boxes)
	return str([filtered_indices, next_bounding_boxes])


@app.route("/updateBoundingBoxes", methods=['POST'])
def updateBoundingBoxes():
	json_request = request.get_json()
	bounding_boxes = BoundingBox.parse_json(json_request["bounding_boxes"])
	tracker.set_bounding_boxes(bounding_boxes)
	return str(bounding_boxes)


@app.route("/predictLabel", methods=['POST'])
def predictLabel():
	json_request = request.get_json()
	json_data = json.dumps(json_request)
	filename = json_request['filename'].split('.')[0]
	os.system("rm {}/*".format(os.path.join(DIR_PATH, "static/images")))
	predicted_label = predict_label(json_data, filename)
	in_fov = os.path.exists(os.path.join(DIR_PATH, "static/images/cropped_image.jpg"))
	return ",".join([str(predicted_label), str(in_fov)])


@app.route("/getMaskRCNNLabels", methods=['POST'])
def getMaskRCNNLabels():
	filename = request.get_json()['fname']
	return str(get_mask_rcnn_labels(filename))


@app.route("/writeOutput", methods=['POST'])
def writeOutput():
	frame = request.get_json()['output']
	fname = frame['filename']
	drivename, fname = fname.split('/')
	fh.save_annotation(drivename, fname, frame["file"])
	return str("hi")


@app.route("/loadFrameNames", methods=['POST'])
def loadFrameNames():
	return fh.get_frame_names()


@app.route("/getFramePointCloud", methods=['POST'])
def getFramePointCloud():
	json_request = request.get_json()
	fname = json_request["fname"]
	drivename, fname = fname.split("/")
	data_str = fh.get_pointcloud(drivename, fname, dtype=str)
	annotation_str = str(fh.load_annotation(drivename, fname, dtype='json'))
	return '?'.join([data_str, annotation_str])


@app.route("/predictBoundingBox", methods=['POST'])
def predictBoundingBox():
	json_request = request.get_json()
	fname = json_request["fname"]
	drivename, fname = fname.split("/")
	point = json_request["point"]
	point = np.array([point['z'], point['x'], point['y']])

	# frame = fh.get_pointcloud(drivename, fname, dtype=float, ground_removed=False)
	# print("num points with ground: {}".format(frame.shape))
	frame = fh.get_pointcloud(drivename, fname, dtype=float, ground_removed=True)
	return str(bp.predict_bounding_box(point, frame))


@app.route("/predictNextFrameBoundingBoxes", methods=['POST'])
def predictNextFrameBoundingBoxes():
	json_request = request.get_json()
	fname = json_request["fname"]
	drivename, fname = fname.split("/")
	frame = fh.load_annotation(drivename, fname)
	res = bp.predict_next_frame_bounding_boxes(frame)
	keys = res.keys()
	for key in keys:
		res[str(key)] = res.pop(key)
	print(res)

	return str(res)


@app.route("/loadAnnotation", methods=['POST'])
def loadAnnotation():
	json_request = request.get_json()
	fname = json_request["fname"]
	frame = fh.load_annotation(fname)
	return str(frame.bounding_boxes)


if __name__ == "__main__":
	fh = FrameHandler()
	bp = BoundingBoxPredictor(fh)
	os.system("rm {}/*".format(os.path.join(DIR_PATH, "static/images")))
	app.run()
