"""Project library used by the recombination engine.

Replace/extend with your own project definitions if you like. Rules the scheduler relies on:
  - every step has hours <= maker_hours_per_day (default 3), because a step must fit inside one evening window
  - step.needs is "maker" (just you), "solder" (soldering station) or "bench" (test bench)
  - step.requires lists project part names that must have ARRIVED before the step can start
"""

DEMO_INVENTORY = [
    {"name": "1000uF 16V electrolytic capacitor", "quantity": 1, "failed": 0},
    {"name": "1N4007 diode", "quantity": 2, "failed": 0},
    {"name": "W10M bridge rectifier", "quantity": 1, "failed": 0},
    {"name": "10k ohm resistor", "quantity": 20, "failed": 0},
    {"name": "5mm LED", "quantity": 2, "failed": 0},
]

PROJECTS = [
    {"key": "usb-power", "name": "USB 5V Power Module", "priority": 1,
     "parts": [{"name": "7805 5V voltage regulator", "qty": 1}, {"name": "1000uF 16V electrolytic capacitor", "qty": 1},
               {"name": "1N4007 diode", "qty": 2}, {"name": "Micro USB connector", "qty": 1}],
     "steps": [
         {"key": "test", "name": "Test salvaged parts", "hours": 1, "needs": "bench", "requires": [], "after": []},
         {"key": "reg", "name": "Solder regulator stage", "hours": 2, "needs": "solder",
          "requires": ["7805 5V voltage regulator", "1N4007 diode"], "after": ["test"]},
         {"key": "cap", "name": "Add filter capacitor", "hours": 1, "needs": "solder",
          "requires": ["1000uF 16V electrolytic capacitor"], "after": ["reg"]},
         {"key": "usb", "name": "Wire USB output", "hours": 2, "needs": "solder",
          "requires": ["Micro USB connector"], "after": ["cap"]},
         {"key": "load", "name": "Load test at 5V", "hours": 1, "needs": "bench", "requires": [], "after": ["usb"]},
     ]},
    {"key": "night-light", "name": "LED Night Light", "priority": 2,
     "parts": [{"name": "5mm LED", "qty": 4}, {"name": "10k ohm resistor", "qty": 4}, {"name": "1N4007 diode", "qty": 1}],
     "steps": [
         {"key": "test", "name": "Test LEDs and resistors", "hours": 1, "needs": "bench", "requires": [], "after": []},
         {"key": "res", "name": "Solder resistor ladder", "hours": 2, "needs": "solder",
          "requires": ["10k ohm resistor", "1N4007 diode"], "after": ["test"]},
         {"key": "led", "name": "Mount LEDs", "hours": 2, "needs": "solder", "requires": ["5mm LED"], "after": ["res"]},
         {"key": "final", "name": "Power-on check", "hours": 1, "needs": "bench", "requires": [], "after": ["led"]},
     ]},
    {"key": "bench-psu", "name": "Mini Bench Supply (5V)", "priority": 3,
     "parts": [{"name": "W10M bridge rectifier", "qty": 1}, {"name": "1000uF 16V electrolytic capacitor", "qty": 2},
               {"name": "7805 5V voltage regulator", "qty": 1}, {"name": "5mm LED", "qty": 1},
               {"name": "10k ohm resistor", "qty": 1}, {"name": "9V 1A mini transformer", "qty": 1}],
     "steps": [
         {"key": "test", "name": "Test rectifier and capacitors", "hours": 1, "needs": "bench", "requires": [], "after": []},
         {"key": "rect", "name": "Wire transformer and rectifier", "hours": 2, "needs": "solder",
          "requires": ["W10M bridge rectifier", "9V 1A mini transformer"], "after": ["test"]},
         {"key": "filter", "name": "Solder filter and regulator", "hours": 3, "needs": "solder",
          "requires": ["1000uF 16V electrolytic capacitor", "7805 5V voltage regulator"], "after": ["rect"]},
         {"key": "led", "name": "Add power LED", "hours": 1, "needs": "solder",
          "requires": ["5mm LED", "10k ohm resistor"], "after": ["filter"]},
         {"key": "load", "name": "Load test", "hours": 1, "needs": "bench", "requires": [], "after": ["led"]},
     ]},
    {"key": "led-flasher", "name": "LED Flasher", "priority": 4,
     "parts": [{"name": "5mm LED", "qty": 2}, {"name": "10k ohm resistor", "qty": 2}, {"name": "1000uF 16V electrolytic capacitor", "qty": 1}],
     "steps": [
         {"key": "test", "name": "Test parts", "hours": 1, "needs": "bench", "requires": [], "after": []},
         {"key": "build", "name": "Solder oscillator", "hours": 2, "needs": "solder",
          "requires": ["5mm LED", "10k ohm resistor", "1000uF 16V electrolytic capacitor"], "after": ["test"]},
         {"key": "check", "name": "Run and tune", "hours": 1, "needs": "bench", "requires": [], "after": ["build"]},
     ]},
    {"key": "rectifier-tester", "name": "Diode Polarity Tester", "priority": 5,
     "parts": [{"name": "1N4007 diode", "qty": 2}, {"name": "5mm LED", "qty": 2}, {"name": "10k ohm resistor", "qty": 2},
               {"name": "Micro USB connector", "qty": 1}],
     "steps": [
         {"key": "test", "name": "Test parts", "hours": 1, "needs": "bench", "requires": [], "after": []},
         {"key": "build", "name": "Solder tester board", "hours": 2, "needs": "solder",
          "requires": ["1N4007 diode", "5mm LED", "10k ohm resistor"], "after": ["test"]},
         {"key": "usb", "name": "Add USB power input", "hours": 1, "needs": "solder", "requires": ["Micro USB connector"], "after": ["build"]},
         {"key": "check", "name": "Verify polarity indication", "hours": 1, "needs": "bench", "requires": [], "after": ["usb"]},
     ]},
]
