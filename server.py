import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neqsim.thermo import fluid, printFrame
from neqsim.process import (compressor, cooler, separator3phase, getProcess,
                            clearProcess, mixer, heater, stream, pump,
                            separator, runProcess, saturator, valve, recycle)

app = FastAPI()

# Oil stabilization process simulation
# https://colab.research.google.com/github/EvenSol/NeqSim-Colab/blob/master/notebooks/process/Simulationofanoilstabilizationprocess.ipynb#scrollTo=vh30bp0h1iuR

class OilStabilizationRequest(BaseModel):
    feedFlowRateWell: float = 10.0  # MSm3/day
    wellPressure: float = 180.0  # bara
    wellTemperature: float = 100.0  # C
    topsidePressure: float = 90.0  # bara
    topsideTemperature: float = 5.0  # C
    firstStagePressure: float = 75.0  # bara
    temperatureOilHeater: float = 75.9  # C
    secondStagePressure: float = 8.6  # bara
    thirdStagePressure: float = 1.9  # bara
    firstStageSuctionCoolerTemperature: float = 25.3  # C
    secondStageSuctionCoolerTemperature: float = 24.5  # C
    thirdStageSuctionCoolerTemperature: float = 25.0  # C
    firstStageExportCoolerTemperature: float = 25.3  # C
    secondStageExportCoolerTemperature: float = 24.5  # C

@app.post("/simulate_process")
def run_oil_stabilization(params: OilStabilizationRequest):
    """
    Simulates a rigorous 3-Stage Crude Oil Stabilization Facility with gas re-compression
    and liquid recycle loops using the NeqSim physics engine.

    PROCESS TOPOLOGY:
    - Separation Train: High-Pressure (1st Stage @ 75 bara), Medium-Pressure (2nd Stage @ 8.6 bara),
      and Low-Pressure (3rd Stage @ 1.9 bara) separation train separates well fluid into Oil and Gas.
    - Stabilization: An Oil Heater is located between the 1st and 2nd stages. Increasing this temperature
      drives off light components (Methane/Ethane) to lower the Oil's True Vapor Pressure (TVP).
    - Gas Re-compression: Low-pressure gas from the 3rd stage is compressed through 2 stages,
      cooled after each stage, and mixed with the main gas stream.
    - Dew Point Control: The combined gas stream is cooled to drop out heavy liquids (NGLs) before export.
    - Recycle Loop: Liquids recovered from gas scrubbers are recycled back to the 3rd Stage Separator
      to maximize liquid recovery.
    - Export Gas Compression: 2-stage compression to 200 bara for pipeline export.

    OPTIMIZATION GOALS:
    - Optimize Heater Temperature (temperatureOilHeater) and Stage Pressures to meet export specifications
    - Balance the trade-off between Oil Quality (TVP), Gas Quality (Cricondenbar), and Power Consumption

    CRITICAL CONSTRAINTS:
    - Oil TVP must be < 0.96 bara for tanker export (typical specification)
    - Gas Cricondenbar must be < 100 bara for pipeline export (typical specification)
    - Trade-off: Higher heater temps improve TVP but increase gas compression power costs

    KEY PARAMETERS TO OPTIMIZE:
    - temperatureOilHeater: Most important for controlling TVP (default 75.9°C)
    - firstStagePressure, secondStagePressure, thirdStagePressure: Control separation efficiency
    - Cooler temperatures: Affect compression power and liquid recovery

    OUTPUT METRICS:
    - tvp_bara: True Vapor Pressure of stabilized oil at 20°C (target: < 0.96 bara)
    - cricondenbar_bara: Cricondenbar of export gas (target: < 100 bara)
    - recomp_power_1_kW, recomp_power_2_kW: Recompression power consumption
    - export_power_1_kW, export_power_2_kW: Export compression power consumption
    - stable_oil_flow_kg_hr: Stabilized oil production rate
    - export_gas_flow_kg_hr: Export gas production rate

    Total simulation time: ~1-50 seconds depending on convergence.
    """
    try:
        clearProcess()

        # Define well fluid
        wellFluid = fluid('pr')
        wellFluid.addComponent("nitrogen", 0.08)
        wellFluid.addComponent("CO2", 3.56)
        wellFluid.addComponent("methane", 87.36)
        wellFluid.addComponent("ethane", 4.02)
        wellFluid.addComponent("propane", 1.54)
        wellFluid.addComponent("i-butane", 0.2)
        wellFluid.addComponent("n-butane", 0.42)
        wellFluid.addComponent("i-pentane", 0.15)
        wellFluid.addComponent("n-pentane", 0.20)

        wellFluid.addTBPfraction("C6", 3.24, 84.99/1000.0, 695.0/1000.0)
        wellFluid.addTBPfraction("C7", 1.34, 97.87/1000.0, 718.0/1000.0)
        wellFluid.addTBPfraction("C8", 1.33, 111.54/1000.0, 729.0/1000.0)
        wellFluid.addTBPfraction("C9", 1.19, 126.1/1000.0, 749.0/1000.0)
        wellFluid.addTBPfraction("C10", 1.15, 140.14/1000.0, 760.0/1000.0)
        wellFluid.addTBPfraction("C11", 1.69, 175.0/1000.0, 830.0/1000.0)
        wellFluid.addTBPfraction("C12", 1.5, 280.0/1000.0, 914.0/1000.0)
        wellFluid.addTBPfraction("C13", 2.103, 560.0/1000.0, 980.0/1000.0)

        wellFluid.setMixingRule(2)
        wellFluid.init(0)

        wellFluid.setMolarComposition([0.08, 3.56, 87.36, 4.02, 1.54, 0.2, 0.42, 0.15, 0.2, 1.24, 1.34, 1.33, 1.19, 1.15, 1.69, 1.5, 1.03])

        # Build process network
        wellStream = stream("dry well stream", wellFluid)
        wellStream.setFlowRate(params.feedFlowRateWell, "MSm3/day")
        wellStream.setTemperature(params.wellTemperature, "C")
        wellStream.setPressure(params.wellPressure, "bara")

        saturatedFeedGas = saturator("water saturator", wellStream)
        waterSaturatedFeedGas = stream("water saturated feed gas", saturatedFeedGas.getOutStream())

        feedTPsetter = heater('inletTP', waterSaturatedFeedGas)
        feedTPsetter.setOutPressure(params.topsidePressure, "bara")
        feedTPsetter.setOutTemperature(params.topsideTemperature, "C")

        chokeValve = valve('valve 1', feedTPsetter.getOutStream())
        chokeValve.setOutletPressure(params.firstStagePressure, 'bara')

        feedToOffshoreProcess = stream("feed to offshore", chokeValve.getOutStream())
        firstStageSeparator = separator3phase("1st stage separator", feedToOffshoreProcess)

        oilHeaterFromFirstStage = heater("oil heater second stage", firstStageSeparator.getOilOutStream())
        oilHeaterFromFirstStage.setOutTemperature(params.temperatureOilHeater,'C')

        oilThrotValve = valve("valve oil from first stage", oilHeaterFromFirstStage.getOutStream())
        oilThrotValve.setOutletPressure(params.secondStagePressure)

        secondStageSeparator = separator3phase("2nd stage separator", oilThrotValve.getOutStream())

        oilThrotValve2 = valve("valve oil from second stage", secondStageSeparator.getOilOutStream())
        oilThrotValve2.setOutletPressure(params.thirdStagePressure)

        thirdStageSeparator = separator3phase("3rd stage separator", oilThrotValve2.getOutStream())

        oilThirdStageToSep = wellStream.clone()
        oilThirdStageToSep.setName("resyc oil")
        thirdStageSeparator.addStream(oilThirdStageToSep)

        stableOil = stream("stable oil", thirdStageSeparator.getOilOutStream())
        stableOilPump = pump("stable oil pump", stableOil, p=15.0)

        firstStageCooler = cooler("1st stage cooler", thirdStageSeparator.getGasOutStream())
        firstStageCooler.setOutTemperature(params.firstStageSuctionCoolerTemperature,'C')

        firstStageScrubber = separator("1st stage scrubber", firstStageCooler.getOutStream())

        firstStageCompressor = compressor("1st stage compressor", firstStageScrubber.getGasOutStream())
        firstStageCompressor.setOutletPressure(params.secondStagePressure)
        firstStageCompressor.setIsentropicEfficiency(0.75)

        secondStageCooler = cooler("2nd stage cooler", firstStageCompressor.getOutStream())
        secondStageCooler.setOutTemperature(params.secondStageSuctionCoolerTemperature,'C')

        secondStageScrubber = separator("2nd stage scrubber", secondStageCooler.getOutStream())

        secondStageCompressor = compressor("2nd stage compressor", secondStageScrubber.getGasOutStream())
        secondStageCompressor.setOutletPressure(params.firstStagePressure)
        secondStageCompressor.setIsentropicEfficiency(0.75)

        richGasMixer = mixer("fourth Stage mixer")
        richGasMixer.addStream(secondStageCompressor.getOutStream())
        richGasMixer.addStream(firstStageSeparator.getGasOutStream())

        dewPointControlCooler = cooler("dew point cooler", richGasMixer.getOutStream())
        dewPointControlCooler.setOutTemperature(params.thirdStageSuctionCoolerTemperature,'C')

        dewPointScrubber = separator("dew point scrubber", dewPointControlCooler.getOutStream())

        lpLiqmixer = mixer("LP liq gas mixer")
        lpLiqmixer.addStream(firstStageScrubber.getLiquidOutStream())
        lpLiqmixer.addStream(secondStageScrubber.getLiquidOutStream())
        lpLiqmixer.addStream(dewPointScrubber.getLiquidOutStream())

        lpResycle = recycle("LP liq resycle")
        lpResycle.addStream(lpLiqmixer.getOutStream())
        lpResycle.setOutletStream(oilThirdStageToSep)

        exportCompressor1 = compressor("export 1st stage", dewPointScrubber.getGasOutStream())
        exportCompressor1.setOutletPressure(140.0)
        exportCompressor1.setIsentropicEfficiency(0.75)

        exportInterstageCooler = cooler("interstage stage cooler", exportCompressor1.getOutStream())
        exportInterstageCooler.setOutTemperature(params.firstStageExportCoolerTemperature,'C')

        exportCompressor2 = compressor("export 2nd stage", exportInterstageCooler.getOutStream())
        exportCompressor2.setOutletPressure(200.0)
        exportCompressor2.setIsentropicEfficiency(0.75)

        exportCooler = cooler("export cooler", exportCompressor1.getOutStream())
        exportCooler.setOutTemperature(params.secondStageExportCoolerTemperature,'C')

        exportGas = stream("export gas", exportCooler.getOutStream())

        # Run simulation
        oilprocess = getProcess()
        thread = oilprocess.runAsThread()
        thread.join(50000)  # max 50 seconds
        if thread.isAlive():
            thread.interrupt()
            thread.join()

        # Extract results
        TVP = stableOil.TVP(20.0, 'C')
        cricondenbar = exportGas.CCB('bara')
        powerComp1 = oilprocess.getUnit("1st stage compressor").getPower() / 1.0e3
        powerComp2 = oilprocess.getUnit("2nd stage compressor").getPower() / 1.0e3
        powerExpComp1 = oilprocess.getUnit("export 1st stage").getPower() / 1.0e3
        powerExpComp2 = oilprocess.getUnit("export 2nd stage").getPower() / 1.0e3

        return {
            "status": "success",
            "tvp_bara": round(TVP, 3),
            "cricondenbar_bara": round(cricondenbar, 3),
            "recomp_power_1_kW": round(powerComp1, 2),
            "recomp_power_2_kW": round(powerComp2, 2),
            "export_power_1_kW": round(powerExpComp1, 2),
            "export_power_2_kW": round(powerExpComp2, 2),
            "stable_oil_flow_kg_hr": round(stableOil.getFlowRate("kg/hr"), 2),
            "export_gas_flow_kg_hr": round(exportGas.getFlowRate("kg/hr"), 2)
        }

    except Exception as e:
        logging.error(f"Simulation failed: {str(e)}")
        return {"status": "error", "message": str(e)}
