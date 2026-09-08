from pydantic import BaseModel, Field, validator
from typing import Optional, Literal

class MetricRow(BaseModel):
    _id: str
    timestamp: str
    heartRate: float
    restingHeartRate: float
    heartRateVariabilitySDNN: float
    oxygenSaturation: float
    respiratoryRate: float
    bodyTemperature: float
    irregularHeartRhythmEvent: int
    ecgClassification: Literal["sinus","afib"]
    ecgAverageHeartRate: int
    sleepAnalysisValue: int
    appleSleepingWristTemperature: float
    numberOfTimesFallen: int
    atrialFibrillationBurden: float
    bloodPressureSystolic: float
    bloodPressureDiastolic: float
    appleWalkingSteadiness: float
    appleWalkingSteadinessEvent: Literal["none","good","bad"]
    forcedExpiratoryVolume1: float
    forcedVitalCapacity: float
    peakExpiratoryFlowRate: float
    bloodGlucose: float
    device: str

    @validator("forcedVitalCapacity")
    def v_fvc(cls, v, values):
        fev1 = values.get("forcedExpiratoryVolume1", 0.0)
        if v <= fev1: 
            raise ValueError("FVC must exceed FEV1")
        return v
