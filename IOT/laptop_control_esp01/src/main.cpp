#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <EEPROM.h>

bool waitingForPicoResponse = false;
unsigned long picoCommandSentTime = 0;
const unsigned long PICO_TIMEOUT = 10000;

// WiFi & MQTT Configuration
String ssid_stored = "";
String password_stored = "";
String control_password_stored = "1234"; // Default control password
bool configMode = false;
int wifiRetries = 0;
const int maxWifiRetries = 5;

// Hosted MQTT Broker settings (using EMQ)
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
const char* mqtt_user = "";
const char* mqtt_password = "";
const char* ducky_topic = "LDrago_windows/ducky_script";

// Magic number to check if EEPROM has valid credentials
const int EEPROM_MAGIC = 0xAB12;

// ===== DEDUPLICATION LOGIC =====
String lastScript = "";
unsigned long lastScriptTime = 0;
const unsigned long SCRIPT_TIMEOUT = 60000; // 60 seconds timeout for script memory

WiFiClient espClient;
PubSubClient client(espClient);
ESP8266WebServer server(80);

// Function declarations
void clearEEPROM();
void loadCredentials();
void saveCredentials(String ssid, String password);
void saveControlPassword(String password);
void loadControlPassword();
bool testWiFiConnection(String ssid, String password);
bool validateControlPassword(String password);
void connectToWiFi();
void startConfigMode();
void setupWebServer();
void handleRoot();
void handleScan();
void handleConnect();
void handleClearWiFi();
void handleSetPassword();
void sendScriptToPico(String script);
void callback(char* topic, byte* payload, unsigned int length);
void reconnect();
bool shouldExecuteScript(String script, bool allowRepeat);
void sendScriptToPico(String script);
void handlePicoResponse();

void sendScriptToPico(String script) {
    // Create JSON format that the Pico expects
    JsonDocument picoDoc;
    picoDoc["ducky_script"] = script;
    String picoMessage;
    serializeJson(picoDoc, picoMessage);

    // Send to Pico via UART (Serial)
    Serial.println("========================================");
    Serial.println("SENDING TO RASPBERRY PI PICO:");
    Serial.println("Raw script: " + script);
    Serial.println("JSON message: " + picoMessage);
    Serial.println("========================================");

    // Send the JSON message to Pico
    Serial.print(picoMessage);
    Serial.print("\n"); // Newline for Pico to detect end of message
    Serial.flush(); // Ensure data is sent immediately

    // Set waiting state for Pico response
    waitingForPicoResponse = true;
    picoCommandSentTime = millis();
    
    Serial.println("⏳ Waiting for Pico execution confirmation...");
}

// Add this new function to handle Pico responses
void handlePicoResponse() {
    if (Serial.available()) {
        String response = Serial.readStringUntil('\n');
        response.trim();
        
        if (response.startsWith("PICO_DONE:")) {
            waitingForPicoResponse = false;
            Serial.println("✅ Pico execution confirmed: " + response);
            
            // Extract execution details
            String executionData = response.substring(10); // Remove "PICO_DONE:"
            
            // Parse execution result
            JsonDocument responseDoc;
            DeserializationError error = deserializeJson(responseDoc, executionData);
            
            if (!error) {
                String command = responseDoc["command"] | "";
                String status = responseDoc["status"] | "";
                long executionTime = responseDoc["execution_time"] | 0;
                
                Serial.println("📊 Execution Summary:");
                Serial.println("   Command: " + command);
                Serial.println("   Status: " + status);
                Serial.println("   Time: " + String(executionTime) + "ms");
                
                // Optional: Send execution confirmation to MQTT for PyAutoGUI
                JsonDocument confirmDoc;
                confirmDoc["esp_id"] = "LDrago_windows";
                confirmDoc["command"] = command;
                confirmDoc["status"] = status;
                confirmDoc["execution_time"] = executionTime;
                confirmDoc["timestamp"] = millis();
                
                String confirmMessage;
                serializeJson(confirmDoc, confirmMessage);
                client.publish("LDrago_windows/pico_execution_done", confirmMessage.c_str());
                
            } else {
                Serial.println("⚠️ Could not parse Pico response");
            }
            
        } else if (response.startsWith("PICO_ERROR:")) {
            waitingForPicoResponse = false;
            Serial.println("❌ Pico execution error: " + response.substring(11));
            
        } else if (response.startsWith("PICO_PROGRESS:")) {
            Serial.println("🔄 Pico progress: " + response.substring(14));
        }
    }
    
    // Check for timeout
    if (waitingForPicoResponse && (millis() - picoCommandSentTime) > PICO_TIMEOUT) {
        waitingForPicoResponse = false;
        Serial.println("⚠️ Pico response timeout - assuming execution completed");
    }
}

void callback(char* topic, byte* payload, unsigned int length) {
  Serial.println("====================================");
  Serial.println("*** ESP01 LAPTOP CONTROLLER ***");
  Serial.print("Message received on topic: ");
  Serial.println(topic);

  // Parse JSON payload
  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, payload, length);
  
  if (error) {
    Serial.print("JSON parsing failed: ");
    Serial.println(error.c_str());
    return;
  }

  String script = doc["script"] | "";
  bool allowRepeat = doc["repeat"] | false; // Default to false for laptop controller
  
  if (script.length() == 0) {
    Serial.println("ERROR: No script provided");
    return;
  }

  // FIRST: Validate control password - highest priority
  String receivedPassword = doc["password"] | "";
  if (!validateControlPassword(receivedPassword)) {
    Serial.println("*** AUTHENTICATION FAILED: Invalid control password ***");
    Serial.println("Expected: " + control_password_stored);
    Serial.println("Received: " + receivedPassword);
    Serial.println("*** COMMAND REJECTED - WRONG PASSWORD ***");
    return;
  }

  Serial.println("✓ Authentication SUCCESS");
  Serial.println("Processing script:");
  Serial.println("Script: " + script);
  Serial.println("Allow Repeat: " + String(allowRepeat ? "true" : "false"));

  // SECOND: Check deduplication logic (only after password validation)
  if (!shouldExecuteScript(script, allowRepeat)) {
    Serial.println("*** SCRIPT REJECTED BY ESP01 - DUPLICATE ***");
    return;
  }

  Serial.println("*** ESP01 SENDING TO PICO ***");
  sendScriptToPico(script);
  Serial.println("====================================");
}

bool shouldExecuteScript(String script, bool allowRepeat) {
  unsigned long currentTime = millis();
  
  Serial.println("=== DEDUPLICATION CHECK ===");
  Serial.println("Current script: " + script);
  Serial.println("Last script: " + lastScript);
  Serial.println("Allow repeat: " + String(allowRepeat));
  Serial.println("Time since last: " + String(currentTime - lastScriptTime) + " ms");
  
  // If repeat is allowed, always execute and reset timeout
  if (allowRepeat) {
    Serial.println("Repeat allowed - executing");
    lastScript = script;
    lastScriptTime = currentTime;
    return true;
  }
  
  // If repeat is NOT allowed, check for duplicates (no timeout clearing)
  if (script == lastScript) {
    Serial.println("*** DUPLICATE DETECTED - REJECTING ***");
    return false;
  }
  
  // New script when repeat=false, update memory and execute
  Serial.println("New script - executing");
  lastScript = script;
  lastScriptTime = currentTime;
  return true;
}

void reconnect() {
  int attempts = 0;
  while (!client.connected() && attempts < 5) {
    Serial.print("Attempting MQTT connection... ");
    
    String clientId = "ESP8266LaptopClient-" + String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str(), mqtt_user, mqtt_password)) {
      Serial.println("CONNECTED!");
      client.subscribe(ducky_topic);
      Serial.println("Subscribed to: " + String(ducky_topic));
    } else {
      Serial.println("FAILED (rc=" + String(client.state()) + ")");
      attempts++;
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  EEPROM.begin(512);
  
  Serial.println("========================================");
  Serial.println("    LAPTOP CONTROL - WIFI SETUP");
  Serial.println("========================================");
  
  // WiFi Setup
  pinMode(0, INPUT_PULLUP); // Reset button
  delay(100);
  
  if (digitalRead(0) == LOW) {
    Serial.println("RESET BUTTON PRESSED - clearing WiFi credentials...");
    clearEEPROM();
    startConfigMode();
    return;
  }
  
  loadCredentials();
  loadControlPassword();
  
  if (ssid_stored.length() > 0 && password_stored.length() > 0) {
    Serial.println("Found stored WiFi: " + ssid_stored);
    
    if (testWiFiConnection(ssid_stored, password_stored)) {
      connectToWiFi();
    } else {
      Serial.println("Stored WiFi invalid. Starting config mode...");
      startConfigMode();
    }
  } else {
    Serial.println("No WiFi credentials. Starting config mode...");
    startConfigMode();
  }
  
  Serial.println("Serial configured for Pico communication at 115200 baud");
  Serial.println("Connect Pico: ESP TX -> Pico RX (GP1), ESP RX -> Pico TX (GP0)");
  Serial.println("Waiting for MQTT commands...");
}

void loop() {
  if (configMode) {
    server.handleClient();
  } else {
    if (!client.connected()) {
      reconnect();
    }
    client.loop();
    
    // ===== HIGH-SPEED FEEDBACK PROCESSING =====
    // Process multiple Pico responses per loop cycle
    int feedbackProcessed = 0;
    while (Serial.available() > 0 && feedbackProcessed < 5) {
      handlePicoResponse();
      feedbackProcessed++;
      delayMicroseconds(100); // Tiny delay between processing
    }
    
    // WiFi health monitoring (less frequent)
    static unsigned long lastWiFiCheck = 0;
    if (millis() - lastWiFiCheck > 1000) { // Check WiFi every 1 second
      if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected! Attempting reconnection...");
        wifiRetries++;
        
        if (wifiRetries >= maxWifiRetries) {
          Serial.println("WiFi failed multiple times. Starting config mode...");
          startConfigMode();
        } else {
          connectToWiFi();
        }
      }
      lastWiFiCheck = millis();
    }
    
    // Timeout management
    if (waitingForPicoResponse && (millis() - picoCommandSentTime) > PICO_TIMEOUT) {
      Serial.println("⏰ Pico timeout - releasing wait");
      waitingForPicoResponse = false;
    }
  }
  
  // Minimal delay for maximum responsiveness
  delay(10); // Ultra-fast loop for real-time feedback
}


// ===== WIFI CONFIGURATION FUNCTIONS =====
void clearEEPROM() {
  Serial.println("Clearing EEPROM...");
  for (int i = 0; i < 512; i++) {
    EEPROM.write(i, 0);
  }
  EEPROM.commit();
  ssid_stored = "";
  password_stored = "";
  control_password_stored = "1234";
  Serial.println("EEPROM cleared successfully!");
}

void loadCredentials() {
  Serial.println("Loading WiFi credentials from EEPROM...");
  
  // Check magic number first
  int magic = (EEPROM.read(200) << 8) | EEPROM.read(201);
  if (magic != EEPROM_MAGIC) {
    Serial.println("No valid credentials found in EEPROM");
    return;
  }
  
  int ssidLength = EEPROM.read(0);
  if (ssidLength > 0 && ssidLength < 100) {
    for (int i = 0; i < ssidLength; i++) {
      ssid_stored += char(EEPROM.read(1 + i));
    }
  }
  
  int passwordLength = EEPROM.read(100);
  if (passwordLength > 0 && passwordLength < 100) {
    for (int i = 0; i < passwordLength; i++) {
      password_stored += char(EEPROM.read(101 + i));
    }
  }
  
  Serial.println("SSID: " + ssid_stored);
}

void loadControlPassword() {
  Serial.println("Loading control password from EEPROM...");
  
  int passwordLength = EEPROM.read(300);
  if (passwordLength > 0 && passwordLength < 50) {
    control_password_stored = "";
    for (int i = 0; i < passwordLength; i++) {
      control_password_stored += char(EEPROM.read(301 + i));
    }
  }
  
  Serial.println("Control password loaded");
}

void saveCredentials(String ssid, String password) {
  Serial.println("Saving WiFi credentials to EEPROM...");
  
  // Clear EEPROM first
  for (int i = 0; i < 512; i++) {
    EEPROM.write(i, 0);
  }
  
  // Save SSID
  EEPROM.write(0, ssid.length());
  for (int i = 0; i < ssid.length(); i++) {
    EEPROM.write(1 + i, ssid[i]);
  }
  
  // Save Password
  EEPROM.write(100, password.length());
  for (int i = 0; i < password.length(); i++) {
    EEPROM.write(101 + i, password[i]);
  }
  
  // Save control password (preserve existing)
  EEPROM.write(300, control_password_stored.length());
  for (int i = 0; i < control_password_stored.length(); i++) {
    EEPROM.write(301 + i, control_password_stored[i]);
  }
  
  // Save magic number to indicate valid credentials
  EEPROM.write(200, (EEPROM_MAGIC >> 8) & 0xFF);
  EEPROM.write(201, EEPROM_MAGIC & 0xFF);
  
  EEPROM.commit();
  Serial.println("Credentials saved successfully!");
}

void saveControlPassword(String password) {
  Serial.println("Saving control password to EEPROM...");
  
  control_password_stored = password;
  
  // Save control password
  EEPROM.write(300, password.length());
  for (int i = 0; i < password.length(); i++) {
    EEPROM.write(301 + i, password[i]);
  }
  
  EEPROM.commit();
  Serial.println("Control password saved successfully!");
}

bool validateControlPassword(String password) {
  return (password == control_password_stored);
}

bool testWiFiConnection(String ssid, String password) {
  Serial.println("Testing WiFi connection...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), password.c_str());
  
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 20) {
    delay(500);
    Serial.print(".");
    timeout++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi test successful!");
    return true;
  } else {
    Serial.println("\nWiFi test failed!");
    WiFi.disconnect();
    return false;
  }
}

void connectToWiFi() {
  Serial.println("Connecting to WiFi: " + ssid_stored);
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid_stored.c_str(), password_stored.c_str());
  
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 40) {
    delay(500);
    Serial.print(".");
    timeout++;
    
    if (timeout >= 40) {
      Serial.println("\nWiFi connection timeout!");
      wifiRetries++;
      return;
    }
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.println("IP address: " + WiFi.localIP().toString());
    Serial.println("Signal strength: " + String(WiFi.RSSI()) + " dBm");
    
    wifiRetries = 0;
    configMode = false;
    
    // Setup MQTT
    client.setServer(mqtt_server, mqtt_port);
    client.setCallback(callback);
  }
}

void startConfigMode() {
  Serial.println("========================================");
  Serial.println("    STARTING WIFI CONFIGURATION MODE");
  Serial.println("========================================");
  
  configMode = true;
  WiFi.mode(WIFI_AP);
  WiFi.softAP("LaptopControl_Config", "12345678");
  
  IPAddress IP = WiFi.softAPIP();
  Serial.println("Configuration AP started");
  Serial.println("SSID: LaptopControl_Config");
  Serial.println("Password: 12345678");
  Serial.println("IP address: " + IP.toString());
  Serial.println("Open browser and go to: http://" + IP.toString());
  Serial.println("========================================");
  
  setupWebServer();
}

void setupWebServer() {
  server.on("/", handleRoot);
  server.on("/scan", handleScan);
  server.on("/connect", handleConnect);
  server.on("/clear", handleClearWiFi);
  server.on("/setpassword", handleSetPassword);
  
  server.begin();
  Serial.println("Web server started on port 80");
}

void handleRoot() {
  String html = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
    <title>Laptop Control WiFi Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; margin: 20px; background: #f0f0f0; }
        .container { max-width: 400px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .form-group { margin-bottom: 15px; position: relative; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 5px; font-size: 16px; cursor: pointer; margin-top: 10px; }
        button:hover { background: #0056b3; }
        .scan-btn { background: #28a745; }
        .scan-btn:hover { background: #1e7e34; }
        .clear-btn { background: #dc3545; }
        .clear-btn:hover { background: #c82333; }
        .password-btn { background: #ffc107; color: #000; }
        .password-btn:hover { background: #e0a800; }
        .show-password { margin-top: 5px; }
        .show-password input[type="checkbox"] { width: auto; margin-right: 5px; }
        .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .loading { color: #007bff; }
        .section { margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Laptop Control Setup</h1>
        
        <div class="section">
            <h2>WiFi Configuration</h2>
            <div class="form-group">
                <button class="scan-btn" onclick="scanNetworks()">Scan for Networks</button>
            </div>
            
            <form id="wifiForm" onsubmit="return connectWiFi(event)">
                <div class="form-group">
                    <label for="ssid">WiFi Network:</label>
                    <select id="ssid" name="ssid" required>
                        <option value="">Select a network...</option>
                    </select>
                </div>
                
                <div class="form-group">
                    <label for="password">WiFi Password:</label>
                    <input type="password" id="password" name="password" placeholder="Enter WiFi password">
                    <div class="show-password">
                        <input type="checkbox" id="showPassword" onchange="togglePassword()">
                        <label for="showPassword">Show password</label>
                    </div>
                </div>
                
                <button type="submit">Connect Device</button>
            </form>
            
            <div class="form-group">
                <button class="clear-btn" onclick="clearWiFi()">Clear Stored WiFi</button>
            </div>
        </div>
        
        <div class="section">
            <h2>Control Password</h2>
            <form id="passwordForm" onsubmit="return setControlPassword(event)">
                <div class="form-group">
                    <label for="controlPassword">Control Password:</label>
                    <input type="password" id="controlPassword" name="controlPassword" placeholder="Enter control password" required>
                    <div class="show-password">
                        <input type="checkbox" id="showControlPassword" onchange="toggleControlPassword()">
                        <label for="showControlPassword">Show password</label>
                    </div>
                </div>
                
                <button type="submit" class="password-btn">Set Control Password</button>
            </form>
        </div>
        
        <div id="status"></div>
    </div>

    <script>
        function togglePassword() {
            const passwordField = document.getElementById('password');
            const showPasswordCheckbox = document.getElementById('showPassword');
            
            if (showPasswordCheckbox.checked) {
                passwordField.type = 'text';
            } else {
                passwordField.type = 'password';
            }
        }

        function toggleControlPassword() {
            const passwordField = document.getElementById('controlPassword');
            const showPasswordCheckbox = document.getElementById('showControlPassword');
            
            if (showPasswordCheckbox.checked) {
                passwordField.type = 'text';
            } else {
                passwordField.type = 'password';
            }
        }

        function scanNetworks() {
            document.getElementById('status').innerHTML = '<div class="status loading">Scanning for networks...</div>';
            
            fetch('/scan')
                .then(response => response.json())
                .then(networks => {
                    const select = document.getElementById('ssid');
                    select.innerHTML = '<option value="">Select a network...</option>';
                    
                    networks.forEach(network => {
                        const option = document.createElement('option');
                        option.value = network.ssid;
                        option.textContent = network.ssid + ' (' + network.rssi + ' dBm)';
                        select.appendChild(option);
                    });
                    
                    document.getElementById('status').innerHTML = '<div class="status success">Found ' + networks.length + ' networks</div>';
                })
                .catch(error => {
                    document.getElementById('status').innerHTML = '<div class="status error">Error scanning: ' + error + '</div>';
                });
        }

        function connectWiFi(event) {
            event.preventDefault();
            
            const ssid = document.getElementById('ssid').value;
            const password = document.getElementById('password').value;
            
            if (!ssid) {
                document.getElementById('status').innerHTML = '<div class="status error">Please select a network</div>';
                return false;
            }
            
            document.getElementById('status').innerHTML = '<div class="status loading">Connecting to ' + ssid + '...</div>';
            
            const formData = new FormData();
            formData.append('ssid', ssid);
            formData.append('password', password);
            
            fetch('/connect', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    document.getElementById('status').innerHTML = '<div class="status success">Connected successfully!<br>IP: ' + result.ip + '<br>Device is now online!</div>';
                    setTimeout(() => {
                        window.location.reload();
                    }, 3000);
                } else {
                    document.getElementById('status').innerHTML = '<div class="status error">Connection failed: ' + result.message + '</div>';
                }
            })
            .catch(error => {
                document.getElementById('status').innerHTML = '<div class="status error">Error: ' + error + '</div>';
            });
            
            return false;
        }

        function setControlPassword(event) {
            event.preventDefault();
            
            const password = document.getElementById('controlPassword').value;
            
            if (password.length < 4) {
                document.getElementById('status').innerHTML = '<div class="status error">Password must be at least 4 characters</div>';
                return false;
            }
            
            document.getElementById('status').innerHTML = '<div class="status loading">Setting control password...</div>';
            
            const formData = new FormData();
            formData.append('controlPassword', password);
            
            fetch('/setpassword', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    document.getElementById('status').innerHTML = '<div class="status success">Control password set successfully!</div>';
                    document.getElementById('controlPassword').value = '';
                } else {
                    document.getElementById('status').innerHTML = '<div class="status error">Failed to set password</div>';
                }
            })
            .catch(error => {
                document.getElementById('status').innerHTML = '<div class="status error">Error: ' + error + '</div>';
            });
            
            return false;
        }

        function clearWiFi() {
            if (confirm('Are you sure you want to clear stored WiFi credentials?')) {
                document.getElementById('status').innerHTML = '<div class="status loading">Clearing WiFi credentials...</div>';
                
                fetch('/clear', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        document.getElementById('status').innerHTML = '<div class="status success">WiFi credentials cleared! Device will restart in config mode.</div>';
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    }
                })
                .catch(error => {
                    document.getElementById('status').innerHTML = '<div class="status error">Clear error: ' + error + '</div>';
                });
            }
        }

        window.onload = function() {
            scanNetworks();
        };
    </script>
</body>
</html>
)rawliteral";

  server.send(200, "text/html", html);
}

void handleScan() {
  Serial.println("Scanning for WiFi networks...");
  int n = WiFi.scanNetworks();
  
  String json = "[";
  for (int i = 0; i < n; i++) {
    if (i > 0) json += ",";
    json += "{";
    json += "\"ssid\":\"" + WiFi.SSID(i) + "\",";
    json += "\"rssi\":" + String(WiFi.RSSI(i));
    json += "}";
  }
  json += "]";
  
  server.send(200, "application/json", json);
}

void handleConnect() {
  String ssid = server.arg("ssid");
  String password = server.arg("password");
  
  Serial.println("Attempting to connect to: " + ssid);
  
  if (testWiFiConnection(ssid, password)) {
    saveCredentials(ssid, password);
    
    String response = "{\"success\":true,\"ip\":\"" + WiFi.localIP().toString() + "\"}";
    server.send(200, "application/json", response);
    
    delay(2000);
    ssid_stored = ssid;
    password_stored = password;
    
    server.stop();
    WiFi.softAPdisconnect(true);
    connectToWiFi();
  } else {
    String response = "{\"success\":false,\"message\":\"Failed to connect\"}";
    server.send(200, "application/json", response);
  }
}

void handleClearWiFi() {
  Serial.println("Clearing WiFi credentials...");
  clearEEPROM();
  
  String response = "{\"success\":true}";
  server.send(200, "application/json", response);
  
  delay(1000);
  ESP.restart();
}

void handleSetPassword() {
  String password = server.arg("controlPassword");
  
  if (password.length() >= 4) {
    saveControlPassword(password);
    
    String response = "{\"success\":true}";
    server.send(200, "application/json", response);
    
    Serial.println("Control password updated successfully");
  } else {
    String response = "{\"success\":false,\"message\":\"Password too short\"}";
    server.send(200, "application/json", response);
  }
}