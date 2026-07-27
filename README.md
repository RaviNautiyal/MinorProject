# Project
# 🫀 HealthFog

### Distributed Fog-Based Heart Disease Prediction System

HealthFog is a distributed AI-based healthcare system designed to perform heart disease risk prediction directly on a local network using **Fog Computing**.

Instead of sending sensitive patient data to a remote cloud server for every prediction, HealthFog distributes inference across multiple local **Fog Worker Nodes**. A central **Master Broker** monitors these workers, routes prediction requests to available nodes, handles worker failures, and maintains a complete trace of prediction requests.

The system combines **Machine Learning, Distributed Systems, REST APIs, Fault-Tolerant Routing, and Healthcare Data Management** into a complete working prototype.

---

## 🚀 Key Features

- ANN-based heart disease prediction
- Master-worker fog computing architecture
- Local AI inference without cloud dependency
- Automatic worker health checking
- Fault-tolerant request routing
- Automatic fallback when a worker goes offline
- Doctor authentication system
- Patient record management
- Real-time fog worker monitoring
- Prediction request tracing
- Route event logging
- Browser-based doctor dashboard
- Multi-machine LAN deployment
- No paid cloud infrastructure required

---

## 🏗️ System Architecture

HealthFog follows a **Master-Worker Fog Architecture**.

```text
                        Doctor
                           │
                           ▼
                 ┌─────────────────┐
                 │ Doctor Dashboard│
                 │ HTML / CSS / JS │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   Master Node   │
                 │     Flask       │
                 │                 │
                 │ Authentication  │
                 │ Patient Records │
                 │ Broker / Router │
                 │ Event Logging   │
                 └───────┬─────────┘
                         │
                  Health Check
                    + Routing
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
      ┌───────────────┐     ┌───────────────┐
      │ Fog Worker 1  │     │ Fog Worker 2  │
      │     Flask     │     │     Flask     │
      │               │     │               │
      │  ANN Model    │     │  ANN Model    │
      │  /predict     │     │  /predict     │
      │  /health      │     │  /health      │
      └───────────────┘     └───────────────┘
```

The Master Node receives requests from the doctor dashboard and checks which Fog Workers are currently available.

The prediction request is then forwarded to an active worker.

If the selected worker becomes unavailable, the Master Node can redirect the request to another available worker.

---

## 🧠 Machine Learning Model

The heart disease prediction model is implemented using an **Artificial Neural Network (ANN)** built with TensorFlow/Keras.

### Input

The model takes **13 clinical features** as input.

### Architecture

```text
13 Input Features
       │
       ▼
Dense Layer - 64 Neurons
ReLU Activation
       │
       ▼
Dropout - 0.3
       │
       ▼
Dense Layer - 32 Neurons
ReLU Activation
       │
       ▼
Dropout - 0.3
       │
       ▼
Dense Layer - 1 Neuron
Sigmoid Activation
       │
       ▼
Heart Disease Risk
```

### Training Configuration

| Parameter | Value |
|---|---|
| Model | Artificial Neural Network |
| Input Features | 13 |
| Hidden Layers | 64 → 32 |
| Activation | ReLU |
| Output Activation | Sigmoid |
| Dropout | 0.3 |
| Optimizer | Adam |
| Learning Rate | 0.001 |
| Loss Function | Binary Cross-Entropy |
| Batch Size | 32 |
| Maximum Epochs | 100 |
| Early Stopping | Patience = 15 |
| Test Accuracy | ~85% |

The trained model is serialized after training and loaded independently by each Fog Worker during startup.

This means workers can perform predictions without retraining the model.

---

## 🌫️ Fog Worker Nodes

Each Fog Worker runs as an independent Flask service.

Every worker loads its own copy of the trained ANN model.

Two main endpoints are provided.

### Prediction Endpoint

```http
POST /predict
```

Example request:

```json
{
    "age": 52,
    "sex": 1,
    "cp": 2,
    "trestbps": 130,
    "chol": 250,
    "fbs": 0,
    "restecg": 1,
    "thalach": 170,
    "exang": 0,
    "oldpeak": 1.2,
    "slope": 2,
    "ca": 0,
    "thal": 2
}
```

The worker:

1. Receives the patient features.
2. Applies the required preprocessing.
3. Passes the feature vector to the ANN.
4. Generates the prediction.
5. Returns the result to the Master Node.

Example response:

```json
{
    "prediction": 1,
    "confidence": 0.87
}
```

---

### Health Endpoint

```http
GET /health
```

This endpoint allows the Master Node to check whether a worker is currently available.

Example response:

```json
{
    "status": "healthy"
}
```

---

## 🔀 Master Broker

The Master Node acts as the central broker of the system.

Before forwarding a prediction request, it checks the availability of registered Fog Workers.

The routing process works approximately as:

```text
Prediction Request
        │
        ▼
Check Worker Health
        │
        ▼
Find Available Workers
        │
        ▼
Select Worker
        │
        ▼
Send Prediction Request
        │
   ┌────┴────┐
   │         │
Success    Failure
   │         │
   ▼         ▼
Return     Try Another
Result       Worker
                │
                ▼
          No Workers Left
                │
                ▼
          Return Error
```

This prevents a single worker failure from immediately stopping the prediction system.

---

## 🔁 Automatic Failover

One of the main features of HealthFog is worker failover.

Suppose:

```text
Worker 1 → ONLINE
Worker 2 → ONLINE
```

The Master Node may route a prediction to Worker 1.

If Worker 1 becomes unavailable:

```text
Worker 1 → OFFLINE
Worker 2 → ONLINE
```

the request can be redirected to Worker 2.

If no worker is available:

```text
Worker 1 → OFFLINE
Worker 2 → OFFLINE
```

the system returns an error instead of generating an unreliable prediction.

---

## 👨‍⚕️ Doctor Dashboard

The browser-based dashboard provides a single interface for doctors to interact with HealthFog.

The dashboard supports:

### Authentication

Doctors can create accounts and securely log into the system.

Passwords are stored using password hashing rather than plain-text storage.

### Patient Management

Doctors can:

- Add patient records
- Enter clinical parameters
- Update existing records
- View stored patient information
- Run predictions

### Worker Monitoring

The dashboard displays the current status of Fog Worker Nodes.

```text
Fog Worker 1    ● ONLINE

Fog Worker 2    ● ONLINE
```

Worker status updates can be delivered using **Server-Sent Events (SSE)**, with HTTP polling used as a fallback where required.

### Prediction Results

After entering the clinical parameters, the doctor can request a prediction directly from the dashboard.

The Master Node forwards the request to an available Fog Worker and returns the prediction result.

---

## 📝 Route Event Logging

HealthFog maintains records of prediction routing events.

A route event can contain information such as:

- Prediction request
- Assigned Fog Worker
- Request status
- Processing result
- Round-trip latency
- Timestamp

This provides traceability for understanding how prediction requests travelled through the distributed system.

---

## 🗄️ Database

SQLite is used by the Master Node for local data storage.

The main tables include:

```text
doctor_accounts
patient_records
route_events
```

### `doctor_accounts`

Stores doctor account information and authentication-related data.

### `patient_records`

Stores patient information and clinical parameters.

### `route_events`

Stores information about routing and prediction requests.

---

## 🖥️ Multi-Machine Deployment

The prototype was tested using **three physical machines connected through a local network**.

```text
Machine 1
Master Node
    │
    ├──────── LAN ──────── Machine 2
    │                     Fog Worker 1
    │
    └──────── LAN ──────── Machine 3
                          Fog Worker 2
```

This setup demonstrates that the architecture can operate as an actual distributed system rather than running every component inside a single process.

Additional Fog Workers can be added by deploying another worker service on machines connected to the same network.

---

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend | Flask |
| Machine Learning | TensorFlow / Keras |
| Model | Artificial Neural Network |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| Communication | REST APIs |
| Live Updates | Server-Sent Events |
| Architecture | Fog Computing / Master-Worker |
| Deployment | Local Area Network |

---

## 📁 Suggested Project Structure

```text
HealthFog/
│
├── master/
│   ├── app.py
│   ├── broker.py
│   ├── database/
│   ├── templates/
│   └── static/
│
├── worker/
│   ├── app.py
│   ├── model/
│   └── scaler/
│
├── model_training/
│   ├── train.py
│   ├── preprocessing.py
│   └── evaluation.py
│
├── screenshots/
│
├── requirements.txt
├── README.md
└── LICENSE
```

Update this section according to the actual folder structure of the repository.

---

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd HealthFog
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

On Linux/macOS:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Running the System

### Start Fog Worker 1

```bash
python worker/app.py
```

Start the second worker on another machine or port.

### Start the Master Node

```bash
python master/app.py
```

Open the Master Node address in the browser.

For multi-machine deployment, ensure all devices are connected to the same LAN and configure the worker addresses inside the Master Node.

---

## 🧪 Testing

The prototype was tested at two levels.

### Model Testing

The ANN was evaluated using a held-out test set.

The model achieved approximately:

```text
Test Accuracy: 85%
```

### System Testing

Functional testing covered:

- Doctor registration
- Doctor login
- Patient record creation
- Patient record update
- ANN prediction
- Worker health detection
- Prediction routing
- Worker failure
- Automatic fallback
- All-workers-offline handling
- Route event logging
- Dashboard updates

---

## ⚠️ Current Limitations

HealthFog is currently a **research/academic prototype** and should not be used for real medical diagnosis.

Some current limitations include:

- Limited heart disease dataset
- Positive-class recall requires improvement
- No TLS between Master and Workers
- No encryption at rest
- No multi-factor authentication
- Workers require network configuration
- Prototype-level security
- Limited large-scale network testing

---

## 🔮 Future Improvements

Future versions of HealthFog can include:

- Improved positive-class recall
- Ensemble learning models
- Gradient-boosted classifiers
- Live ECG data integration
- Dynamic Fog Worker registration
- Automatic worker discovery
- TLS-encrypted communication
- Role-based access control
- Multi-factor authentication
- Encrypted patient storage
- Containerized worker deployment
- Larger-scale fog network testing
- Improved load-balancing strategies

---

## 🎯 Project Objective

The main objective of HealthFog is to demonstrate that AI-based healthcare inference does not always need to depend completely on remote cloud infrastructure.

By bringing model inference closer to the clinical environment, the project explores how **Fog Computing + Machine Learning + Distributed Systems** can be combined to create a low-cost and fault-tolerant healthcare prediction platform.

---

## ⚕️ Disclaimer

HealthFog is an academic prototype developed for educational and research purposes.

The predictions generated by the system **must not be considered medical advice or a clinical diagnosis**. The system has not been clinically validated and should not be used for real patient treatment decisions.

---

## 👤 Author

**Ravi Nautiyal**

B.Tech — Computer Science and Engineering  
Dr. B. R. Ambedkar National Institute of Technology, Jalandhar

---

## ⭐ Support

If you find the project useful or interesting, consider giving the repository a ⭐.
