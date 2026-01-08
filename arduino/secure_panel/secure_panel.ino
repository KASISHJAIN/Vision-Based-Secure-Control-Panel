enum State { IDLE, ARMED, ACTIVE, ALERT };
State currentState = IDLE;

// const int RedPin = 13;
// const int BluePin = 12;
// const int GreenPin = 11;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);
  // pinMode(RedPin, OUTPUT);
  // pinMode(BluePin, OUTPUT);
  // pinMode(GreenPin, OUTPUT);
}

void loop() {

  //check if data exists
  if(Serial.available()) {
    //read one full command
    String cmd = Serial.readStringUntil('\n');
    //sanitize it
    cmd.trim();
    //compare against allowed commands
    //act only if current state allows it
    if(currentState == IDLE && cmd == "ARM") {
      currentState = ARMED;
    }
    else if (currentState == ARMED && cmd == "ACTIVATE") {
      currentState = ACTIVE;
    }
    else if ((currentState == ARMED || currentState == ACTIVE) && cmd == "STOP") {
      currentState = ALERT;
    }

  }
  
  



  // put your main code here, to run repeatedly:
  // digitalWrite(RedPin, HIGH);
  // digitalWrite(BluePin, HIGH);
  // digitalWrite(GreenPin, HIGH);
  // delay(1000);
  // digitalWrite(RedPin, LOW);
  // digitalWrite(BluePin, LOW);
  // digitalWrite(GreenPin, LOW);
  // delay(1000);
}
