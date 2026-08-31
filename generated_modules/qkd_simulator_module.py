import asyncio
import hashlib
import json
import logging
import os
import random
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("qkd_simulator_module")


class QKDSimulator:
    """Simulates the BB84 Quantum Key Distribution (QKD) protocol."""

    def __init__(
        self,
        num_bits: int = 1000,
        channel_error_rate: float = 0.05,
        eavesdropper_present: bool = False,
        privacy_amplification_factor: float = 0.5,
        qber_threshold: float = 0.11,
    ):
        self.num_bits = max(1, num_bits)
        self.channel_error_rate = max(0.0, min(1.0, channel_error_rate))
        self.eavesdropper_present = eavesdropper_present
        self.privacy_amplification_factor = max(
            0.0, min(1.0, privacy_amplification_factor)
        )
        self.qber_threshold = qber_threshold

    def step1_alice_generate(self) -> Tuple[List[int], List[int]]:
        """Generate random classical bits and random measurement basis selections for Alice.

        Basis representation: 0 = Rectilinear (+), 1 = Diagonal (x)
        """
        alice_bits = [random.choice([0, 1]) for _ in range(self.num_bits)]
        alice_bases = [random.choice([0, 1]) for _ in range(self.num_bits)]
        return alice_bits, alice_bases

    def step2_step3_channel_propagation(
        self, alice_bits: List[int], alice_bases: List[int]
    ) -> Tuple[List[int], List[int]]:
        """Encode Alice's bits into quantum states and simulate propagation.

        Applies intercept-resend eavesdropping by Eve (if present) and
        depolarizing channel noise.
        """
        states_bits = list(alice_bits)
        states_bases = list(alice_bases)

        # Optional Intercept-Resend Eavesdropping by Eve
        if self.eavesdropper_present:
            eve_bases = [random.choice([0, 1]) for _ in range(self.num_bits)]
            for i in range(self.num_bits):
                if eve_bases[i] != states_bases[i]:
                    # Eve measures in wrong basis -> alters quantum state randomly
                    states_bits[i] = random.choice([0, 1])
                    states_bases[i] = eve_bases[i]

        # Depolarizing Quantum Channel Noise
        for i in range(self.num_bits):
            if random.random() < self.channel_error_rate:
                states_bits[i] = 1 - states_bits[i]

        return states_bits, states_bases

    def step4_bob_measure(
        self, states_bits: List[int], states_bases: List[int]
    ) -> Tuple[List[int], List[int]]:
        """Simulate Bob's measurement of incoming quantum states using random bases."""
        bob_bases = [random.choice([0, 1]) for _ in range(self.num_bits)]
        bob_bits = []

        for i in range(self.num_bits):
            if bob_bases[i] == states_bases[i]:
                bob_bits.append(states_bits[i])
            else:
                bob_bits.append(random.choice([0, 1]))

        return bob_bits, bob_bases

    def step5_sifting(
        self,
        alice_bits: List[int],
        alice_bases: List[int],
        bob_bits: List[int],
        bob_bases: List[int],
    ) -> Tuple[List[int], List[int]]:
        """Perform key sifting by discarding bits where bases mismatched."""
        sifted_alice = []
        sifted_bob = []
        for a_bit, a_base, b_bit, b_base in zip(
            alice_bits, alice_bases, bob_bits, bob_bases
        ):
            if a_base == b_base:
                sifted_alice.append(a_bit)
                sifted_bob.append(b_bit)
        return sifted_alice, sifted_bob

    def step6_7_calculate_qber_and_detect(
        self, sifted_alice: List[int], sifted_bob: List[int]
    ) -> Tuple[float, bool, List[int], List[int]]:
        """Calculate Quantum Bit Error Rate (QBER) on a sample and detect eavesdropper."""
        if not sifted_alice:
            return 0.0, False, [], []

        # Sample 50% of the sifted key for QBER estimation
        sample_size = len(sifted_alice) // 2
        if sample_size == 0:
            sample_size = len(sifted_alice)

        errors = sum(
            1
            for a, b in zip(
                sifted_alice[:sample_size], sifted_bob[:sample_size]
            )
            if a != b
        )
        qber = errors / float(sample_size)

        eavesdropper_detected = qber > self.qber_threshold

        # Remaining key after sample parameter estimation
        remaining_alice = sifted_alice[sample_size:]
        remaining_bob = sifted_bob[sample_size:]

        return qber, eavesdropper_detected, remaining_alice, remaining_bob

    def step8_distill_final_key(
        self, raw_key_bits: List[int], eavesdropper_detected: bool
    ) -> str:
        """Apply error correction and privacy amplification to produce the final secret key."""
        if eavesdropper_detected or not raw_key_bits:
            return ""

        bit_string = "".join(map(str, raw_key_bits))
        target_bit_len = max(
            8, int(len(raw_key_bits) * self.privacy_amplification_factor)
        )

        # Hash-based privacy amplification (SHA-256)
        hash_digest = hashlib.sha256(bit_string.encode("utf-8")).hexdigest()

        # Convert target bit length into hex character count (4 bits per hex char)
        hex_char_count = max(1, target_bit_len // 4)
        return hash_digest[:hex_char_count]

    def run(self) -> Dict[str, Any]:
        """Run complete QKD simulation workflow."""
        alice_bits, alice_bases = self.step1_alice_generate()
        chan_bits, chan_bases = self.step2_step3_channel_propagation(
            alice_bits, alice_bases
        )
        bob_bits, bob_bases = self.step4_bob_measure(chan_bits, chan_bases)

        sifted_alice, sifted_bob = self.step5_sifting(
            alice_bits, alice_bases, bob_bits, bob_bases
        )
        sifted_key_length = len(sifted_alice)

        qber, eavesdropper_detected, remaining_alice, _ = (
            self.step6_7_calculate_qber_and_detect(sifted_alice, sifted_bob)
        )

        final_secret_key = self.step8_distill_final_key(
            remaining_alice, eavesdropper_detected
        )

        return {
            "sifted_key_length": sifted_key_length,
            "quantum_bit_error_rate": round(qber, 4),
            "eavesdropper_detected": eavesdropper_detected,
            "final_secret_key": final_secret_key,
        }


async def execute(query: str, context: dict = None) -> str:
    """Asynchronous entry point for executing the QKD simulator.

    Args:
        query: JSON string or text input containing simulation parameters.
        context: Optional dictionary containing execution context / inputs.

    Returns:
        JSON string representing the simulation outputs or error details.
    """
    try:
        context = context or {}

        # Attempt to parse query string as JSON parameters if provided
        query_params = {}
        if query and isinstance(query, str):
            try:
                parsed = json.loads(query)
                if isinstance(parsed, dict):
                    query_params = parsed
            except json.JSONDecodeError:
                logger.debug(
                    "Query is not JSON formatted. Relying on context/defaults."
                )

        # Extract parameters prioritizing context -> query -> defaults
        num_bits = int(
            context.get(
                "num_bits", query_params.get("num_bits", 1000)
            )
        )
        channel_error_rate = float(
            context.get(
                "channel_error_rate",
                query_params.get("channel_error_rate", 0.05),
            )
        )
        eavesdropper_present = bool(
            context.get(
                "eavesdropper_present",
                query_params.get("eavesdropper_present", False),
            )
        )
        privacy_amplification_factor = float(
            context.get(
                "privacy_amplification_factor",
                query_params.get("privacy_amplification_factor", 0.5),
            )
        )

        logger.info(
            f"Executing QKD simulation: num_bits={num_bits}, "
            f"channel_error_rate={channel_error_rate}, "
            f"eavesdropper_present={eavesdropper_present}, "
            f"privacy_amplification_factor={privacy_amplification_factor}"
        )

        # Offload CPU-bound simulation logic to worker thread
        simulator = QKDSimulator(
            num_bits=num_bits,
            channel_error_rate=channel_error_rate,
            eavesdropper_present=eavesdropper_present,
            privacy_amplification_factor=privacy_amplification_factor,
        )

        result = await asyncio.to_thread(simulator.run)

        logger.info("QKD simulation finished successfully.")
        return json.dumps(result, indent=2)

    except Exception as e:
        error_msg = f"QKD Simulation failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"error": error_msg})