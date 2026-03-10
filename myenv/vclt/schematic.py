from vclt.config import logger


def generate_complex_circuit_netlist(topology, components):
    logger.warning("Topology %s is not implemented yet. Falling back to basic_circuit.", topology)
    fallback = {
        "topology": "basic_circuit",
        "V": components.get("V", 5),
        "R": components.get("R", 1),
        "C": components.get("C", 2),
    }
    return generate_circuit_schematic(fallback)


def generate_circuit_schematic(components):
    topology = components.get("topology", "basic_circuit")
    complex_topologies = {
        "common_emitter",
        "boost_converter",
        "astable_multivibrator",
        "wien_oscillator",
        "full_bridge_rectifier",
    }
    if topology in complex_topologies:
        return generate_complex_circuit_netlist(topology, components)

    def fmt(val):
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        if isinstance(val, int):
            return str(val)
        try:
            fval = float(val)
            if fval.is_integer():
                return str(int(fval))
        except Exception:
            pass
        return str(val)

    schematic = ["Version 4.1", "SHEET 1 880 680"]

    if topology == "low_pass_filter":
        schematic.extend([
            "WIRE 208 48 80 48",
            "WIRE 400 48 288 48",
            "WIRE 80 112 80 48",
            "WIRE 400 112 400 48",
            "WIRE 80 272 80 192",
            "WIRE 400 272 400 176",
            "FLAG 80 272 0",
            "FLAG 400 272 0",
            "FLAG 400 48 OUT",
            "SYMBOL voltage 80 96 R0",
            "WINDOW 123 24 124 Left 2",
            "WINDOW 39 0 0 Left 2",
            "SYMATTR Value2 AC 1",
            "SYMATTR InstName Vin",
        ])
        v_type = components.get("V_type", "SINE")
        if v_type == "SINE":
            schematic.append(f"SYMATTR Value {v_type}(1 {fmt(components.get('V', 1))} {fmt(components.get('freq', 25000))})")
        else:
            schematic.append(f"SYMATTR Value {fmt(components.get('V', 1))}")
        schematic.extend([
            "SYMBOL res 304 32 R90",
            "WINDOW 0 0 56 VBottom 2",
            "WINDOW 3 32 56 VTop 2",
            "SYMATTR InstName R1",
            f"SYMATTR Value {fmt(components.get('R', 1))}",
            "SYMBOL cap 384 112 R0",
            "SYMATTR InstName C1",
            f"SYMATTR Value {fmt(components.get('C', 100e-6))}",
            "TEXT 72 328 Left 2 !.tran 0 0.1 0 0.0001",
            "TEXT 72 352 Left 2 !.ac dec 100 1 100k",
        ])
    elif topology == "high_pass_filter":
        schematic.extend([
            "WIRE 192 48 80 48",
            "WIRE 352 48 256 48",
            "WIRE 464 48 352 48",
            "WIRE 80 112 80 48",
            "WIRE 352 112 352 48",
            "WIRE 80 272 80 192",
            "WIRE 352 272 352 192",
            "FLAG 80 272 0",
            "FLAG 352 272 0",
            "FLAG 464 48 Output_high_pass",
            "IOPIN 464 48 Out",
            "SYMBOL voltage 80 96 R0",
            "WINDOW 123 24 124 Left 2",
            "WINDOW 39 0 0 Left 2",
            "SYMATTR Value2 AC 1",
            "SYMATTR InstName Vin",
        ])
        v_type = components.get("V_type", "SINE")
        if v_type == "SINE":
            schematic.append(f"SYMATTR Value {v_type}(1 {fmt(components.get('V', 1))} {fmt(components.get('freq', 25000))})")
        else:
            schematic.append(f"SYMATTR Value {fmt(components.get('V', 1))}")
        schematic.extend([
            "SYMBOL res 336 96 R0",
            "SYMATTR InstName R1",
            f"SYMATTR Value {fmt(components.get('R', 1))}",
            "SYMBOL cap 192 64 R270",
            "WINDOW 0 32 32 VTop 2",
            "WINDOW 3 0 32 VBottom 2",
            "SYMATTR InstName C1",
            f"SYMATTR Value {fmt(components.get('C', 100e-6))}",
            "TEXT 464 264 Left 2 !.ac dec 1000 10 100k",
        ])
    elif topology == "band_pass_filter":
        schematic.extend([
            "WIRE 176 48 80 48",
            "WIRE 352 48 240 48",
            "WIRE 448 48 352 48",
            "WIRE 592 48 528 48",
            "WIRE 80 112 80 48",
            "WIRE 352 112 352 48",
            "WIRE 592 112 592 48",
            "WIRE 80 272 80 192",
            "WIRE 352 272 352 192",
            "WIRE 592 272 592 176",
            "FLAG 80 272 0",
            "FLAG 352 272 0",
            "FLAG 592 272 0",
            "FLAG 592 48 OUT",
            "SYMBOL voltage 80 96 R0",
            "WINDOW 123 24 124 Left 2",
            "WINDOW 39 0 0 Left 2",
            "SYMATTR Value2 AC 1",
            "SYMATTR InstName V1",
        ])
        v_type = components.get("V_type", "SINE")
        if v_type == "SINE":
            schematic.append(f"SYMATTR Value {v_type}(1 {fmt(components.get('V', 1))} {fmt(components.get('freq', 25000))})")
        else:
            schematic.append(f"SYMATTR Value {fmt(components.get('V', 1))}")
        schematic.extend([
            "SYMBOL res 544 32 R90",
            "WINDOW 0 0 56 VBottom 2",
            "WINDOW 3 32 56 VTop 2",
            "SYMATTR InstName R1",
            f"SYMATTR Value {fmt(components.get('R1', 1))}",
            "SYMBOL cap 576 112 R0",
            "SYMATTR InstName C1",
            f"SYMATTR Value {fmt(components.get('C1', 100e-6))}",
            "SYMBOL cap 240 32 R90",
            "WINDOW 0 0 32 VBottom 2",
            "WINDOW 3 32 32 VTop 2",
            "SYMATTR InstName C2",
            f"SYMATTR Value {fmt(components.get('C2', 100e-6))}",
            "SYMBOL res 336 96 R0",
            "SYMATTR InstName R2",
            f"SYMATTR Value {fmt(components.get('R2', 1))}",
            "TEXT 80 320 Left 2 !.tran 0 0.1 0 0.0001",
            "TEXT 80 344 Left 2 !.ac dec 100 1 100k",
        ])
    else:
        schematic.extend([
            "WIRE 208 128 64 128",
            "WIRE 64 160 64 128",
            "WIRE 208 240 208 208",
            "WIRE 64 304 64 240",
            "WIRE 208 304 64 304",
            "WIRE 208 320 208 304",
            "FLAG 208 320 0",
            "SYMBOL voltage 64 144 R0",
            "SYMATTR InstName V1",
            "SYMATTR Value 5",
            "SYMBOL res 192 112 R0",
            "SYMATTR InstName R1",
            "SYMATTR Value 1",
            "SYMBOL cap 192 240 R0",
            "SYMATTR InstName C1",
            "SYMATTR Value 2",
            "TEXT 24 344 Left 2 !.tran 10",
        ])

    return "\\n".join(schematic)
