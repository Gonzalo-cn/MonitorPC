import psutil
import socket
import platform
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

# Variables para almacenar los datos históricos
ram_history = []
cpu_history = []
network_history = []

# Función para obtener la información del servidor local
def get_local_server_info():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    os_info = platform.system() + " " + platform.release()
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disks = psutil.disk_partitions()
    disk_usage = {}
    cpu_percent = psutil.cpu_percent(interval=1)
    load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
    boot_time_timestamp = psutil.boot_time()
    bt = datetime.fromtimestamp(boot_time_timestamp)
    uptime = datetime.now() - bt
    temperature = psutil.sensors_temperatures() if hasattr(psutil, 'sensors_temperatures') else {'coretemp': [{'current': 'N/A'}]}

    for disk in disks:
        try:
            usage = psutil.disk_usage(disk.mountpoint)
            disk_usage[disk.device] = usage
        except PermissionError:
            continue

    return {
        "name": hostname,
        "ip": ip_address,
        "os": os_info,
        "status": "Encendido",
        "memory": memory,
        "swap": swap,
        "disk_usage": disk_usage,
        "cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(),
        "load_avg": load_avg,
        "uptime": str(uptime).split('.')[0],  # Remover microsegundos
        "temperature": temperature['coretemp'][0]['current'] if 'coretemp' in temperature and temperature['coretemp'] else 'N/A'
    }

def get_network_info():
    net_io = psutil.net_io_counters()
    return {
        "bytes_sent": net_io.bytes_sent / (1024 ** 2),  # Convertir a MB
        "bytes_recv": net_io.bytes_recv / (1024 ** 2)   # Convertir a MB
    }

def get_top_processes():
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
        processes.append(proc.info)
    # Ordenar los procesos por uso de CPU y memoria
    processes = sorted(processes, key=lambda x: (x['cpu_percent'], x['memory_percent']), reverse=True)[:10]
    return processes

# Ruta para la página principal
@app.route('/')
def index():
    server_info = [get_local_server_info()]
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Monitorización de Servidor Local</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/materialize/1.0.0/css/materialize.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" rel="stylesheet">
        <style>
            body {
                background-color: #f5f5f5;
                color: #000000;
            }
            .card {
                background-color: #ffffff;
                margin-bottom: 20px;
                border-radius: 4px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                display: flex;
                flex-direction: column;
                height: auto;
                padding: 20px;
            }
            .card-title {
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 10px;
                color: #000000;
            }
            .progress {
                height: 15px;
                background-color: #e0e0e0;
            }
            .determinate {
                background-color: #6200ee;
            }
            .determinate.yellow {
                background-color: yellow !important;
            }
            .status-encendido {
                color: green;
                font-weight: bold;
            }
            .status-apagado {
                color: red;
                font-weight: bold;
            }
            .chart-container {
                position: relative;
                height: 150px; /* Ajusta la altura de los gráficos */
                width: 100%;
            }
            .charts-row {
                display: flex;
                justify-content: space-between;
                margin-top: 20px;
            }
            .chart-item {
                width: 48%;
            }
            .value-display-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 10px;
            }
            .value-display {
                font-size: 16px;
                font-weight: bold;
                text-align: center;
            }
            .row {
                display: flex;
                flex-wrap: wrap;
            }
            .col {
                flex: 0 0 100%; /* Ancho completo para una sola tarjeta por fila */
                max-width: 100%;
                box-sizing: border-box;
                padding: 10px;
            }
            .icon-text {
                display: flex;
                align-items: center;
            }
            .icon-text i {
                margin-right: 5px;
            }
            .process-table {
                width: 100%;
                margin-top: 20px;
                border-collapse: collapse;
            }
            .process-table th, .process-table td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            .process-table th {
                background-color: #6200ee;
                color: white;
            }
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            function refreshData() {
                fetch('/data')
                    .then(response => response.json())
                    .then(data => {
                        // Actualizar gráfico de RAM
                        let ramChart = window['ramChart'];
                        ramChart.data.labels = data.labels;
                        ramChart.data.datasets[0].data = data.servers[0].ram;
                        ramChart.update();
                        document.getElementById('ramUsage').innerText = data.servers[0].ram[data.servers[0].ram.length - 1].toFixed(1) + ' GB Usado';
                        document.getElementById('ramFree').innerText = data.servers[0].ram_free.toFixed(1) + ' GB Libre';

                        // Actualizar gráfico de CPU
                        let cpuChart = window['cpuChart'];
                        cpuChart.data.labels = data.labels;
                        cpuChart.data.datasets[0].data = data.servers[0].cpu;
                        cpuChart.update();
                        document.getElementById('cpuUsage').innerText = data.servers[0].cpu[data.servers[0].cpu.length - 1].toFixed(1) + '% Usado';
                        document.getElementById('cpuFree').innerText = (100 - data.servers[0].cpu[data.servers[0].cpu.length - 1]).toFixed(1) + '% Libre';

                        // Actualizar gráfico de red
                        let networkChart = window['networkChart'];
                        networkChart.data.labels = data.labels;
                        networkChart.data.datasets[0].data = data.servers[0].network.map(n => n.sent);
                        networkChart.data.datasets[1].data = data.servers[0].network.map(n => n.recv);
                        networkChart.update();
                        document.getElementById('networkSent').innerText = data.servers[0].network[data.servers[0].network.length - 1].sent.toFixed(1) + ' MB Enviado';
                        document.getElementById('networkRecv').innerText = data.servers[0].network[data.servers[0].network.length - 1].recv.toFixed(1) + ' MB Recibido';

                        // Actualizar información de discos
                        data.servers[0].disk_usage.forEach((disk, diskIndex) => {
                            document.getElementById(`diskUsed${diskIndex}`).innerText = disk.used.toFixed(2) + ' GB Usados';
                            document.getElementById(`diskFree${diskIndex}`).innerText = disk.free.toFixed(2) + ' GB Libres';
                            document.getElementById(`diskProgress${diskIndex}`).style.width = (disk.used / (disk.total + disk.free) * 100) + '%';
                            document.getElementById(`diskProgress${diskIndex}`).className = 'determinate ' + (disk.free / (disk.total + disk.free) * 100 < 5 ? 'red' : '');
                        });

                        // Actualizar tabla de procesos
                        let processTableBody = document.getElementById('processTableBody');
                        processTableBody.innerHTML = '';
                        data.processes.forEach(proc => {
                            let row = document.createElement('tr');
                            row.innerHTML = `
                                <td>${proc.pid}</td>
                                <td>${proc.name}</td>
                                <td>${proc.username}</td>
                                <td>${proc.cpu_percent.toFixed(1)}</td>
                                <td>${proc.memory_percent.toFixed(1)}</td>
                                <td>${proc.status}</td>
                            `;
                            processTableBody.appendChild(row);
                        });

                        // Actualizar otros datos
                        document.getElementById('uptime').innerText = data.servers[0].uptime;
                        document.getElementById('temperature').innerText = data.servers[0].temperature + ' °C';
                        document.getElementById('loadAvg1').innerText = data.servers[0].load_avg[0].toFixed(2);
                        document.getElementById('loadAvg5').innerText = data.servers[0].load_avg[1].toFixed(2);
                        document.getElementById('loadAvg15').innerText = data.servers[0].load_avg[2].toFixed(2);
                        document.getElementById('swapUsed').innerText = (data.servers[0].swap.used / (1024 ** 3)).toFixed(1) + ' GB Usado';
                        document.getElementById('swapFree').innerText = (data.servers[0].swap.free / (1024 ** 3)).toFixed(1) + ' GB Libre';
                    });
            }
            setInterval(refreshData, 15000); // Refrescar cada 15 segundos

            document.addEventListener('DOMContentLoaded', function() {
                let ctxRam = document.getElementById('ramUsageChart').getContext('2d');
                let ctxCpu = document.getElementById('cpuUsageChart').getContext('2d');
                let ctxNetwork = document.getElementById('networkUsageChart').getContext('2d');

                window['ramChart'] = new Chart(ctxRam, {
                    type: 'line',
                    data: {
                        labels: [], // Etiquetas vacías iniciales
                        datasets: [{
                            label: 'Uso de RAM',
                            data: [],
                            fill: true,
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });

                window['cpuChart'] = new Chart(ctxCpu, {
                    type: 'line',
                    data: {
                        labels: [], // Etiquetas vacías iniciales
                        datasets: [{
                            label: 'Uso de CPU',
                            data: [],
                            fill: true,
                            backgroundColor: 'rgba(255, 193, 7, 0.2)', // Cambio a amarillo
                            borderColor: 'rgba(255, 193, 7, 1)', // Cambio a amarillo
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });

                window['networkChart'] = new Chart(ctxNetwork, {
                    type: 'line',
                    data: {
                        labels: [], // Etiquetas vacías iniciales
                        datasets: [
                            {
                                label: 'Enviado',
                                data: [],
                                fill: true,
                                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                borderWidth: 1
                            },
                            {
                                label: 'Recibido',
                                data: [],
                                fill: true,
                                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                                borderColor: 'rgba(255, 99, 132, 1)',
                                borderWidth: 1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true
                            }
                        }
                    }
                });

                refreshData(); // Inicializar los datos en la carga de la página
            });
        </script>
    </head>
    <body>
        <div class="container">
            <div class="row">
                {% for server in servers %}
                <div class="col s12 m6 l4">
                    <div class="card">
                        <div class="card-content">
                            <span class="card-title">{{ server.name }}</span>
                            <p><strong>Dirección IP:</strong> {{ server.ip }} | <strong>Sistema Operativo:</strong> {{ server.os }}</p>
                            <p><strong>Estado:</strong> <span class="status-encendido">{{ server.status }}</span></p>
                            <p><strong>Tiempo de Actividad:</strong> <span id="uptime">{{ server.uptime }}</span></p>
                            <p><strong>Temperatura CPU:</strong> <span id="temperature">{{ server.temperature }} °C</span></p>
                            <p><strong>Carga Promedio (1 min):</strong> <span id="loadAvg1">{{ server.load_avg[0] }}</span></p>
                            <p><strong>Carga Promedio (5 min):</strong> <span id="loadAvg5">{{ server.load_avg[1] }}</span></p>
                            <p><strong>Carga Promedio (15 min):</strong> <span id="loadAvg15">{{ server.load_avg[2] }}</span></p>
                            <p class="icon-text"><i class="fas fa-memory"></i> <strong>RAM Total:</strong> {{ (server.memory.total / (1024 ** 3)) | round(1) }} GB | <i class="fas fa-microchip"></i> <strong>CPUs Totales:</strong> {{ server.cpu_count }}</p>
                            <p class="icon-text"><strong>Swap Usado:</strong> <span id="swapUsed">{{ (server.swap.used / (1024 ** 3)) | round(1) }} GB</span> | <strong>Swap Libre:</strong> <span id="swapFree">{{ (server.swap.free / (1024 ** 3)) | round(1) }} GB</span></p>
                            <span class="card-title">Espacio en Disco</span>
                            {% for disk, usage in server.disk_usage.items() %}
                                <p><strong>Disco {{ disk }}:</strong> 
                                    <span id="diskUsed{{ loop.index0 }}">{{ (usage.used / (1024 ** 3)) | round(2) }} GB Usados</span> / 
                                    <span id="diskFree{{ loop.index0 }}">{{ (usage.free / (1024 ** 3)) | round(2) }} GB Libres</span>
                                </p>
                                <div class="progress">
                                    <div id="diskProgress{{ loop.index0 }}" class="determinate {% if (usage.free / usage.total) * 100 < 5 %}red{% endif %}" style="width: {{ (usage.used / usage.total) * 100 }}%;"></div>
                                </div>
                            {% endfor %}
                            <div class="charts-row">
                                <div class="chart-item">
                                    <span class="card-title">Uso de RAM</span>
                                    <div class="value-display-row">
                                        <div id="ramUsage" class="value-display">0 GB Usado</div>
                                        <div id="ramFree" class="value-display">0 GB Libre</div>
                                    </div>
                                    <div class="chart-container">
                                        <canvas id="ramUsageChart"></canvas>
                                    </div>
                                </div>
                                <div class="chart-item">
                                    <span class="card-title">Uso de CPU</span>
                                    <div class="value-display-row">
                                        <div id="cpuUsage" class="value-display">0% Usado</div>
                                        <div id="cpuFree" class="value-display">0% Libre</div>
                                    </div>
                                    <div class="chart-container">
                                        <canvas id="cpuUsageChart"></canvas>
                                    </div>
                                </div>
                                <div class="chart-item">
                                    <span class="card-title">Uso de Red</span>
                                    <div class="value-display-row">
                                        <div id="networkSent" class="value-display">0 MB Enviado</div>
                                        <div id="networkRecv" class="value-display">0 MB Recibido</div>
                                    </div>
                                    <div class="chart-container">
                                        <canvas id="networkUsageChart"></canvas>
                                    </div>
                                </div>
                            </div>
                            <div>
                                <span class="card-title">Procesos Principales</span>
                                <table class="process-table">
                                    <thead>
                                        <tr>
                                            <th>PID</th>
                                            <th>Nombre</th>
                                            <th>Usuario</th>
                                            <th>CPU (%)</th>
                                            <th>Memoria (%)</th>
                                            <th>Estado</th>
                                        </tr>
                                    </thead>
                                    <tbody id="processTableBody">
                                        <!-- Filas de procesos se llenarán aquí -->
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </body>
    </html>
    ''', servers=server_info)

# Ruta para los datos del servidor
@app.route('/data')
def data():
    global ram_history, cpu_history, network_history

    server_info = [get_local_server_info()]
    network_info = get_network_info()
    top_processes = get_top_processes()

    # Calcular el uso de RAM en GB
    ram_used_gb = server_info[0]['memory'].used / (1024 ** 3)
    ram_free_gb = server_info[0]['memory'].available / (1024 ** 3)
    cpu_percent = server_info[0]['cpu_percent']
    bytes_sent = network_info['bytes_sent']
    bytes_recv = network_info['bytes_recv']

    # Agregar datos actuales a la historia
    ram_history.append(ram_used_gb)
    cpu_history.append(cpu_percent)
    network_history.append({"sent": bytes_sent, "recv": bytes_recv})

    # Mantener solo los últimos 20 puntos de datos
    if len(ram_history) > 20:
        ram_history = ram_history[-20:]
    if len(cpu_history) > 20:
        cpu_history = cpu_history[-20:]
    if len(network_history) > 20:
        network_history = network_history[-20:]

    labels = list(range(len(ram_history)))  # Etiquetas simples basadas en el número de puntos de datos

    # Preparar la información de los discos
    disk_usage = [{
        'used': usage.used / (1024 ** 3),
        'free': usage.free / (1024 ** 3),
        'total': usage.total / (1024 ** 3)
    } for usage in server_info[0]['disk_usage'].values()]

    servers_data = {
        'labels': labels,
        'ram': ram_history,
        'ram_free': ram_free_gb,
        'cpu': cpu_history,
        'network': network_history,
        'disk_usage': disk_usage,
        'swap': server_info[0]['swap'],
        'load_avg': server_info[0]['load_avg'],
        'uptime': server_info[0]['uptime'],
        'temperature': server_info[0]['temperature']
    }

    return jsonify({
        'labels': labels,
        'servers': [servers_data],
        'processes': top_processes
    })

if __name__ == '__main__':
    app.run(debug=True)