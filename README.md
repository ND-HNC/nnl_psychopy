# nnl_psychopy

Demonstrate a PsychoPy task capable of interfacing with Nordic Neuro Lab's SyncBox.


## Usage

- Within PsychoPy, `import nordic_neuro_lab` and start an instance of the `SyncBox` class.
- Capture input with the `get_trigger` and `get_response` methods.
- See nnl_2afc.psyexp for component integration.

```python
import nordic_neuro_lab

# Initiate connection with syncbox and start listening
sync_box = nordic_neuro_lab.SyncBox(
    num_volumes=21, # num(TR)+1 = 63s
    num_slices=1,
    trigger_slice=1,
    trigger_volume=1,
    pulse_length=100,
    tr_time=3000,
    optional_trigger_slice=0,
    optional_trigger_volume=0,
    simulation=False,
    manual_mode=False, # Switch to True to start syncbox session manually
)
sync_box.start()

# Capture responses for start screen
resp, _, _ = sync_box.get_response(0, timeout=0.001)
if resp and resp in ['a', 'b', 'c', 'd']:
    continueRoutine = False
    thisComponent.status = FINISHED

# Wait for sync pulse
trigger = sync_box.get_trigger(timeout=None)
if trigger in ["s"]:
    continueRoutine = False

# Get responses from task screen
resp, rt, dur = sync_box.get_response(begin_time, timeout=0.001)
if resp:
    key_2afc.keys = resp
    key_2afc.rt = rt
    key_2afc.duration = dur

# Disconnect
sync_box.stop()
sync_box.close()
```

## File Descriptions

- Task Files
    - StimSet: SetC of Stark's Behavioral Pattern Separation Task, found [here](https://faculty.sites.uci.edu/starklab/mnemonic-similarity-task-mst/).
    - nnl_2afc.psyexp: Example PsychoPy two AFC experiment file, with added Custom Code components to demonstrate integration and use of nordic_neuro_lab.py.
    - nnl_2afc.py: Generated python script for PsychoPy experiment file.
- Interface Files
    - nordic_neuro_lab.py: Python module to be imported and used to connect PsychoPy to SyncBox.
    - test_nordic_neuro_lab.py: Unit tests.
    - (serial_keyboard.py: Deprecated.)
    - (test_serial_keyabord.py: Deprecated unit tests.)
