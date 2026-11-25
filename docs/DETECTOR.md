# Maize and Weed Detection for a Low-Cost Weeding Robot

This repository contains the code for a study of maize and weed detection on Nigerian field images. A compact YOLO26n detector was trained on a dataset merged from five public sources, including 500 annotated Nigerian images, and tested under eight training-data conditions to see how much local data matters. The trained model runs on a Raspberry Pi 4 robot that looks for weeds with a camera and protects nearby maize, and in a small web app where anyone can try it on their own photos.

The notebooks reproduce the full study: dataset building, training of the main models, the eight training-data conditions, per-source evaluation, paired bootstrap confidence intervals and an offline simulation of the robot's targeting rule.

## Repository layout

```
app.py, detector.py         Streamlit demo app (photo, camera, live camera, video and robot view)
requirements.txt            packages for the demo app
packages.txt                system packages for Streamlit Community Cloud
.streamlit/config.toml      app theme
models/
  maize_weed_yolo26n_ncnn_416/   YOLO26n exported to NCNN at 416 px, with robot_config.json (thresholds)
  maize_weed_yolo11n_ncnn_416/   YOLO11n, same format, for comparison
samples/                    example images from the datasets for trying the app
notebooks/
  01_build_dataset.ipynb    download the five sources, convert labels, split, save the dataset (Colab, CPU)
  02_train_export.ipynb     train YOLO26n or YOLO11n, evaluate, pick robot thresholds, export NCNN models (Colab, T4 GPU)
  03_experiments.ipynb      the eight training-data runs and all analyses (Colab, T4 GPU)
robot/
  weed_robot.py             camera -> detector -> filters -> maize protection -> weed tracking -> fire command
  robot_drive.py            follows a driving route and pauses while a weed is targeted
  find_zone.py              finds where the indicator LEDs (laser stand-in) point in the camera image
  src/test_motors.py        L298N motor driver and route language used by robot_drive.py
  src/motor_config.json     motor pins, limits and trim
  requirements-pi.txt
```

The datasets and the PyTorch training weights are not stored here. The notebooks download or create them in Google Drive.

## Demo app

The app runs the same NCNN model that runs on the robot. Upload a photo, take one with the camera, use the live camera or upload a video, and it draws the maize and weed boxes and shows what the robot would do: every maize plant gets a safety zone, weeds touching a zone are skipped and all other weeds become targets. The sidebar switches between the two models and adjusts the confidence thresholds. When the app runs on a laptop on the same network as the robot, the last tab shows the robot's live camera view.

Run it locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

To put it online, create a new app on [Streamlit Community Cloud](https://share.streamlit.io), choose this repository and set the main file to `app.py`. The app installs the packages in `requirements.txt` and `packages.txt` itself.

The app works best with photos taken from above, 40 to 60 cm over the plants, in daylight. The model has only seen field scenes, so indoor or non-plant photos can give random boxes.

## Datasets

| Source | Location | Images used | Licence |
|---|---|---|---|
| [Maize-Weed Image dataset](https://data.mendeley.com/datasets/jjbfcckrsp/2) (annotated part) | Niger State, Nigeria | 500 | CC BY 4.0 |
| [CornWeed](https://zenodo.org/records/7961764) | Germany | 3,574 | see record |
| [CropAndWeed](https://github.com/cropandweed/cropandweed-dataset) (images containing maize) | Austria | 1,834 | non-commercial research only |
| [ACRE Crop-Weed](https://zenodo.org/records/8102217) (maize fields) | France | 500 | CC BY 4.0 |
| [corn-weed, Roboflow Universe](https://universe.roboflow.com/emad-yousry/corn-weed) | not stated | 900 | CC BY 4.0 |

All labels are mapped to two classes: maize, and weed (any other plant). Soil and crop-row labels are dropped. Splits are fixed and deterministic. Nigerian, ACRE and CornWeed images are grouped in blocks of ten consecutive frame numbers before hashing, CropAndWeed images are grouped by recording session, CornWeed's official validation set is used as its test set, and the Roboflow images keep their own split. Notebook 01 downloads the newest Roboflow version available when it runs. Each dataset, including the sample images in `samples/`, stays under its own licence.

## Reproducing the results

Everything except the robot runs in Google Colab, so no local installation is needed. All three notebooks save to one Google Drive folder, `MyDrive/maize_weed/`.

1. **Build the dataset.** Open `notebooks/01_build_dataset.ipynb` in Colab on a CPU runtime. Paste a free Roboflow API key into `ROBOFLOW_API_KEY` in the settings cell, then run all cells. Do not commit the notebook with your key in it. The download is about 26 GB to Colab's disk. The output is `maizeweed_dataset.zip` (7,308 images: 5,156 train, 956 validation, 1,196 test) plus dataset figures and tables.
2. **Train the two main models.** Open `notebooks/02_train_export.ipynb` on a T4 GPU runtime. Run it with `MODEL = 'yolo26n.pt'`, then again with `MODEL = 'yolo11n.pt'`. Each run trains for 100 epochs at 640 px, chooses the robot thresholds on the Nigerian validation images and exports NCNN models for the Pi (`maize_weed_yolo26n_ncnn_416.zip` and so on). The thresholds chosen this way were maize 0.278 / weed 0.25 for YOLO26n and 0.20 / 0.31 for YOLO11n, and the models in `models/` come from these runs.
3. **Run the experiments.** Open `notebooks/03_experiments.ipynb` on a T4 GPU runtime. Section 2 trains the eight 50-epoch YOLO26n conditions (about 1.5 hours each; finished runs are skipped and interrupted runs resume). Sections 3 to 6 compute per-source scores, patch-aware scoring, paired bootstrap intervals and the targeting simulation, and Section 8 writes the summary tables to `MyDrive/maize_weed/experiments/`.

Software used: Ultralytics 8.4 (notebooks 02 and 03 pin 8.4.202), Python 3.13 and an NVIDIA T4 GPU in Colab. Because training on a GPU is not bit-for-bit deterministic, retrained models can differ slightly from one run to the next.

## Running the robot

Hardware: Raspberry Pi 4 (64-bit Raspberry Pi OS), OV5647 camera, L298N motor driver with four wheel motors on a separate battery, and indicator LEDs standing in for the laser.

| Part | GPIO (BCM) |
|---|---|
| Left motors (ENA, IN1, IN2) | 12, 17, 27 |
| Right motors (ENB, IN3, IN4) | 13, 22, 23 |
| Indicator LEDs (each with a 330 ohm resistor to GND) | 24 |

Connect the Pi's GND to the motor driver's GND. A heatsink and fan are recommended, since the Pi throttles during long runs without cooling.

**Setup on the Pi**

```bash
git clone <this repository>
cd <repository>/robot
python3 -m venv --system-site-packages venv    # keeps picamera2, gpiozero and lgpio from the OS visible
source venv/bin/activate
pip install -r requirements-pi.txt
```

Installing CPU-only PyTorch first (`pip install torch --index-url https://download.pytorch.org/whl/cpu`) avoids a large CUDA download. `weed_robot.py` uses the YOLO26n model in `models/` by default; pass `--model-dir` to use another one.

**Run**

```bash
python weed_robot.py                              # detection and LEDs only, robot stays still
python weed_robot.py --source ../samples/         # test on a folder of photos, no camera needed
python weed_robot.py --drive --motors-dry-run     # full program, wheels do not move
python weed_robot.py --drive                      # drive the route, stop for weeds, light the LEDs, continue
```

Open `http://<pi-address>:8000` in a browser on the same network to see the live view. Each fire command is logged to `logs/actions_<date>.csv`. Stop with Ctrl+C, which also stops the motors and LEDs.

Useful options: `--roi x1,y1,x2,y2` limits firing to part of the image (`find_zone.py` can measure it), `--persist N` sets how many frames in a row a weed must be seen, `--maize-conf` and `--weed-conf` override the thresholds, `--route "forward 5 35, right 1 45, forward 5 35"` changes the route and `--record 5` saves a frame every 5 seconds for future training data. Run `python weed_robot.py --help` for the full list.

Motor tests with the wheels off the ground: `python robot_drive.py --dry-run`, `python robot_drive.py` and `python robot_drive.py --pause-test`.

On the Pi, the YOLO26n NCNN model at 416 px took about 145 ms per frame (around 7 frames per second).

## Limitations

Each training condition was trained once, so the confidence intervals cover the choice of test images but not run-to-run variation. The Nigerian test set has 60 images from one region and season. The targeting results come from an offline simulation on still images, not from a field trial.
