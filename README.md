# PPG Heart Disease Detection System

## Overview
This project is an IoT-based real-time PPG (Photoplethysmography) monitoring and arrhythmia pattern classification system using:

- ESP32
- MAX30102 PPG Sensor
- SH1106 OLED Display
- Flask API Server
- React Native / Expo Mobile App
- Machine Learning (Random Forest)

The system acquires live PPG signals from the MAX30102 sensor, displays the waveform on OLED and mobile app, and performs arrhythmia-related pattern classification using a trained ML model.

---

## Features
- Real-time PPG acquisition
- OLED live waveform display
- Mobile application visualization
- BPM estimation
- Flask backend API
- Random Forest based arrhythmia classification
- PhysioNet 2015 ICU waveform dataset integration

---

## Hardware Used
| Component | Purpose |
|---|---|
| ESP32 | Main microcontroller |
| MAX30102 | PPG sensor |
| SH1106 OLED | Live waveform display |
| WiFi | Communication with server |

---

## Software Stack
- Arduino IDE
- Python
- Flask
- React Native (Expo)
- Scikit-learn
- NumPy
- Pandas

---

## Dataset
Dataset used:
PhysioNet / Computing in Cardiology Challenge 2015 Dataset

Signals used:
- PLETH (PPG waveform)

Labels:
- Asystole
- Bradycardia
- Tachycardia
- Ventricular Tachycardia
- Ventricular Flutter/Fibrillation

---

## Workflow
1. Acquire PPG signal from MAX30102
2. Send signal to Flask API
3. Preprocess waveform
4. Extract features
5. Perform ML prediction
6. Display result on mobile app and OLED

---

## Limitations
- Prototype system only
- Not clinically validated
- Domain mismatch between ICU data and wearable sensor
- PPG is less accurate than ECG for arrhythmia diagnosis

---

## Future Improvements
- Deep Learning models
- Better wearable datasets
- TinyML deployment
- ECG integration
- Cloud database integration

---

## Author
Harsh Mishra  
VNIT Nagpur
