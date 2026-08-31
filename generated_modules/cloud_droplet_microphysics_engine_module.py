"""
Cloud Droplet Microphysics Engine Module
========================================

Executes intrinsic thermodynamic and droplet mechanics equations to simulate 
cloud microphysical processes and perform comparative analysis against empirical 
cloud observations.
"""

import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple

# Configure module-level logger
logger = logging.getLogger("cloud_droplet_microphysics_engine_module")

# Physical Constants
R_D = 287.05          # Specific gas constant for dry air (J/kg K)
R_V = 461.5           # Specific gas constant for water vapor (J/kg K)
CP_D = 1005.0         # Specific heat of dry air at constant pressure (J/kg K)
G = 9.80665           # Acceleration due to gravity (m/s^2)
RHO_W = 1000.0        # Density of liquid water (kg/m^3)
M_W = 0.018015        # Molecular weight of water (kg/mol)
SIGMA_W = 0.0728      # Surface tension of water-air interface (N/m)
UNIVERSAL_GAS_CONST = 8.31446 # Universal gas constant (J/mol K)


class ThermodynamicCalculator:
    """Calculates atmospheric thermodynamics, vapor pressures, and moist parcel dynamics."""

    @staticmethod
    def saturation_vapor_pressure(temp_k: float) -> float:
        """Bolton (1980) formulation for saturation vapor pressure over liquid water (Pa)."""
        temp_c = temp_k - 273.15
        return 611.2 * math.exp((17.67 * temp_c) / (temp_c + 243.5))

    @staticmethod
    def latent_heat_vaporization(temp_k: float) -> float:
        """Temperature-dependent latent heat of vaporization (J/kg)."""
        temp_c = temp_k - 273.15
        return 2.501e6 - 2370.0 * temp_c

    @staticmethod
    def air_density(pressure_pa: float, temp_k: float) -> float:
        """Calculates dry air density (kg/m^3)."""
        return pressure_pa / (R_D * temp_k)

    @staticmethod
    def vapor_diffusivity(temp_k: float, pressure_pa: float) -> float:
        """Water vapor diffusivity in air (m^2/s)."""
        return 2.11e-5 * ((temp_k / 273.15) ** 1.94) * (101325.0 / pressure_pa)

    @staticmethod
    def thermal_conductivity(temp_k: float) -> float:
        """Thermal conductivity of air (W/m K)."""
        temp_c = temp_k - 273.15
        return 4.184 * (5.69 + 0.017 * temp_c) * 1e-3


class KohlerTheoryEngine:
    """Calculates aerosol activation and equilibrium supersaturation via Köhler Theory."""

    def __init__(self, hygroscopicity_kappa: float):
        self.kappa = hygroscopicity_kappa

    def kelvin_parameter_a(self, temp_k: float) -> float:
        """Calculates the curvature (Kelvin) parameter A (m)."""
        return (2.0 * SIGMA_W * M_W) / (RHO_W * UNIVERSAL_GAS_CONST * temp_k)

    def equilibrium_supersaturation(self, radius_m: float, dry_radius_m: float, temp_k: float) -> float:
        """
        Computes Köhler equilibrium supersaturation ratio (S_eq - 1).
        Using kappa-Köhler theory approximation: S_eq = (r^3 - r_d^3)/(r^3 - r_d^3*(1-kappa)) * exp(A/r)
        """
        if radius_m <= dry_radius_m:
            return 0.0
        
        a_param = self.kelvin_parameter_a(temp_k)
        curvature_term = math.exp(a_param / radius_m)
        solute_term = (radius_m**3 - dry_radius_m**3) / (radius_m**3 - dry_radius_m**3 * (1.0 - self.kappa))
        
        s_eq = solute_term * curvature_term
        return s_eq - 1.0

    def critical_supersaturation(self, dry_radius_m: float, temp_k: float) -> float:
        """Computes critical supersaturation for activation given dry aerosol radius and kappa."""
        a_param = self.kelvin_parameter_a(temp_k)
        s_crit = math.sqrt((4.0 * (a_param**3)) / (27.0 * self.kappa * (dry_radius_m**3)))
        return s_crit


class DropletDynamicsEngine:
    """Calculates droplet condensational growth, coalescence, and hydrodynamic velocities."""

    @staticmethod
    def terminal_velocity(radius_m: float, air_density: float) -> float:
        """
        Calculates droplet terminal fall velocity (m/s).
        Stokes' Law for small droplets (r < 40 um), transitioning to empirical fits.
        """
        dynamic_viscosity = 1.81e-5  # Pa s
        if radius_m < 40e-6:
            # Stokes Regime
            return (2.0 * RHO_W * G * (radius_m**2)) / (9.0 * dynamic_viscosity)
        else:
            # Intermediate formulation approximation
            return 8000.0 * radius_m  # Linearized regime for small drizzle drops

    @staticmethod
    def condensational_growth_rate(
        radius_m: float,
        supersaturation: float,
        temp_k: float,
        pressure_pa: float
    ) -> float:
        """
        Computes dr/dt (m/s) based on the diffusional droplet growth equation:
        r * dr/dt = (S - 1) / (F_k + F_d)
        """
        if radius_m <= 1e-9:
            return 0.0

        l_v = ThermodynamicCalculator.latent_heat_vaporization(temp_k)
        e_sat = ThermodynamicCalculator.saturation_vapor_pressure(temp_k)
        k_a = ThermodynamicCalculator.thermal_conductivity(temp_k)
        d_v = ThermodynamicCalculator.vapor_diffusivity(temp_k, pressure_pa)

        # Thermal conduction term F_k
        f_k = ((l_v / (R_V * temp_k)) - 1.0) * (l_v * RHO_W / (k_a * temp_k))
        # Vapor diffusion term F_d
        f_d = (RHO_W * R_V * temp_k) / (e_sat * d_v)

        growth_factor = 1.0 / (f_k + f_d)
        dr_dt = (supersaturation / radius_m) * growth_factor
        return dr_dt


class CloudMicrophysicsSimulator:
    """Simulates cloud parcel ascent, thermodynamics, DSD evolution, and entrainment."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.kappa = config.get("aerosol_activation_parameters", {}).get("hygroscopicity_kappa", 0.3)
        self.dry_radius = config.get("aerosol_activation_parameters", {}).get("mean_dry_radius_m", 0.05e-6)
        self.entrainment_rate = config.get("entrainment_rate_m1", 1.0e-4) # m^-1
        self.updraft_velocity = config.get("updraft_velocity_ms", 2.0)     # m/s
        self.kohler = KohlerTheoryEngine(self.kappa)

    def run_simulation(
        self,
        thermo_profile: List[Dict[str, float]],
        initial_dsd: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Simulates parcel ascent along height levels.
        Returns modeled cloud profile and droplet growth rate histories.
        """
        modeled_profile = []
        growth_rates_history = []

        # Parse initial conditions from input profile
        base_level = thermo_profile[0]
        temp = base_level["temperature_k"]
        pressure = base_level["pressure_pa"]
        relative_humidity = base_level["relative_humidity"]
        
        # Parse initial DSD bins
        bin_radii = list(initial_dsd.get("bin_radii_m", [1e-6, 5e-6, 10e-6, 20e-6, 30e-6]))
        bin_counts = list(initial_dsd.get("bin_concentrations_m3", [1e8, 5e7, 1e7, 1e6, 1e4]))

        current_alt = base_level.get("altitude_m", 0.0)
        num_levels = len(thermo_profile)

        for i in range(num_levels):
            target_alt = thermo_profile[i]["altitude_m"]
            dz = target_alt - current_alt if i > 0 else 0.0
            dt = dz / self.updraft_velocity if self.updraft_velocity > 0 else 0.0

            # Calculate ambient equilibrium state
            e_sat = ThermodynamicCalculator.saturation_vapor_pressure(temp)
            q_sat = (0.622 * e_sat) / (pressure - 0.378 * e_sat)
            
            # Estimate supersaturation
            s_ambient = relative_humidity - 1.0

            # Calculate activation state
            s_crit = self.kohler.critical_supersaturation(self.dry_radius, temp)

            # Growth rate calculations for each bin
            current_growth_rates = []
            updated_radii = []
            
            total_lwc = 0.0
            num_sum = 0.0
            den_sum = 0.0

            for r, n in zip(bin_radii, bin_counts):
                # Apply condensational growth
                dr_dt = DropletDynamicsEngine.condensational_growth_rate(
                    radius_m=r,
                    supersaturation=s_ambient,
                    temp_k=temp,
                    pressure_pa=pressure
                )
                r_new = max(self.dry_radius, r + dr_dt * dt)
                
                # Terminal velocity
                air_dens = ThermodynamicCalculator.air_density(pressure, temp)
                v_t = DropletDynamicsEngine.terminal_velocity(r_new, air_dens)

                current_growth_rates.append({
                    "radius_m": r_new,
                    "dr_dt_m_s": dr_dt,
                    "terminal_velocity_m_s": v_t
                })
                
                updated_radii.append(r_new)

                # Moment metrics (LWC, Effective Radius)
                droplet_vol = (4.0 / 3.0) * math.pi * (r_new ** 3)
                total_lwc += n * droplet_vol * RHO_W  # kg/m^3
                
                num_sum += n * (r_new ** 3)
                den_sum += n * (r_new ** 2)

            bin_radii = updated_radii
            
            # Bulk Cloud Metrics
            effective_radius = (num_sum / den_sum) if den_sum > 0 else 0.0
            total_number_density = sum(bin_counts)

            # Update parcel thermodynamics for next step with dry adiabatic lapse + entrainment cooling
            if dz > 0:
                l_v = ThermodynamicCalculator.latent_heat_vaporization(temp)
                # Entrainment mixing effect (dilution of RH and LWC)
                relative_humidity -= self.entrainment_rate * (relative_humidity - 0.70) * dz
                
                # Pseudo-adiabatic temp gradient approximation
                dT_dz = -(G / CP_D) * (1.0 + (l_v * q_sat) / (R_D * temp)) / (1.0 + ((l_v**2 * q_sat * 0.622) / (CP_D * R_D * temp**2)))
                temp += dT_dz * dz
                pressure -= ThermodynamicCalculator.air_density(pressure, temp) * G * dz
                current_alt = target_alt

            modeled_profile.append({
                "altitude_m": target_alt,
                "temperature_k": temp,
                "pressure_pa": pressure,
                "supersaturation": s_ambient,
                "effective_radius_m": effective_radius,
                "liquid_water_content_kg_m3": total_lwc,
                "total_number_density_m3": total_number_density
            })

            growth_rates_history.append({
                "altitude_m": target_alt,
                "bin_growth_rates": current_growth_rates
            })

        return modeled_profile, growth_rates_history


class ObservationalComparator:
    """Performs statistical cross-comparison between modeled and empirical cloud dataset observations."""

    @staticmethod
    def evaluate(
        modeled_profile: List[Dict[str, Any]],
        observed_profile: List[Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Computes residuals, RMSE, MBE, and comparison matrix."""
        
        matrix = []
        lwc_residuals = []
        reff_residuals = []

        # Create altitude lookup for observations
        obs_map = {round(obs["altitude_m"], 1): obs for obs in observed_profile}

        for mode in modeled_profile:
            alt = round(mode["altitude_m"], 1)
            if alt in obs_map:
                obs = obs_map[alt]
                
                lwc_mod = mode["liquid_water_content_kg_m3"]
                lwc_obs = obs.get("liquid_water_content_kg_m3", 0.0)
                lwc_res = lwc_mod - lwc_obs
                lwc_residuals.append(lwc_res)

                reff_mod = mode["effective_radius_m"]
                reff_obs = obs.get("effective_radius_m", 0.0)
                reff_res = reff_mod - reff_obs
                reff_residuals.append(reff_res)

                matrix.append({
                    "altitude_m": alt,
                    "modeled_lwc_kg_m3": lwc_mod,
                    "observed_lwc_kg_m3": lwc_obs,
                    "lwc_residual": lwc_res,
                    "modeled_effective_radius_m": reff_mod,
                    "observed_effective_radius_m": reff_obs,
                    "effective_radius_residual": reff_res
                })

        # Calculate performance statistics
        def calculate_stats(residuals: List[float]) -> Dict[str, float]:
            if not residuals:
                return {"rmse": 0.0, "mbe": 0.0, "mae": 0.0}
            n = len(residuals)
            mbe = sum(residuals) / n
            mae = sum(abs(r) for r in residuals) / n
            rmse = math.sqrt(sum(r**2 for r in residuals) / n)
            return {"rmse": rmse, "mbe": mbe, "mae": mae}

        summary_metrics = {
            "samples_compared": len(matrix),
            "lwc_statistics": calculate_stats(lwc_residuals),
            "effective_radius_statistics": calculate_stats(reff_residuals)
        }

        return matrix, summary_metrics


def _generate_default_inputs() -> Dict[str, Any]:
    """Generates synthetic atmospheric baseline data if context inputs are omitted."""
    altitudes = [500.0, 750.0, 1000.0, 1250.0, 1500.0, 1750.0, 2000.0]
    
    ambient_profile = []
    observed_profile = []

    for idx, alt in enumerate(altitudes):
        temp = 288.15 - (0.0065 * alt)
        pressure = 101325.0 * ((1.0 - 2.25577e-5 * alt) ** 5.25588)
        rh = min(1.005, 0.95 + (idx * 0.012))

        ambient_profile.append({
            "altitude_m": alt,
            "temperature_k": temp,
            "pressure_pa": pressure,
            "relative_humidity": rh
        })

        # Synthetic observations with realistic variation
        observed_profile.append({
            "altitude_m": alt,
            "liquid_water_content_kg_m3": 0.0002 * (idx + 1),
            "effective_radius_m": (8.0 + (idx * 0.8)) * 1e-6
        })

    dsd_initial = {
        "bin_radii_m": [2e-6, 5e-6, 10e-6, 15e-6, 25e-6],
        "bin_concentrations_m3": [2.0e8, 1.0e8, 3.0e7, 5.0e6, 1.0e5]
    }

    aerosol_params = {
        "hygroscopicity_kappa": 0.3,
        "mean_dry_radius_m": 0.04e-6
    }

    return {
        "ambient_thermodynamic_profile": ambient_profile,
        "observational_cloud_data": observed_profile,
        "droplet_size_distribution_initial": dsd_initial,
        "aerosol_activation_parameters": aerosol_params
    }


async def execute(query: str, context: Optional[dict] = None) -> str:
    """
    Asynchronous primary execution entry point for the cloud microphysics engine.

    Args:
        query (str): Query string or JSON payload specifying execution options.
        context (dict, optional): Dictionary containing input profiles and parameters:
            - observational_cloud_data
            - ambient_thermodynamic_profile
            - droplet_size_distribution_initial
            - aerosol_activation_parameters

    Returns:
        str: JSON string containing theoretical growth rates, modeled profiles,
             comparison matrices, and microphysical summary metrics.
    """
    logger.info("Executing Cloud Droplet Microphysics Engine execution workflow...")
    
    try:
        # Step 1: Input Normalization & Defaults Extraction
        ctx = context or {}
        
        # Check if query is JSON string overriding parameters
        if query and query.strip().startswith("{"):
            try:
                parsed_query = json.loads(query)
                if isinstance(parsed_query, dict):
                    ctx.update(parsed_query)
            except json.JSONDecodeError:
                logger.warning("Query provided as string but failed to parse as JSON. Using defaults.")

        defaults = _generate_default_inputs()
        
        ambient_profile = ctx.get("ambient_thermodynamic_profile", defaults["ambient_thermodynamic_profile"])
        observed_data = ctx.get("observational_cloud_data", defaults["observational_cloud_data"])
        initial_dsd = ctx.get("droplet_size_distribution_initial", defaults["droplet_size_distribution_initial"])
        aerosol_params = ctx.get("aerosol_activation_parameters", defaults["aerosol_activation_parameters"])

        sim_config = {
            "aerosol_activation_parameters": aerosol_params,
            "entrainment_rate_m1": ctx.get("entrainment_rate_m1", 1.2e-4),
            "updraft_velocity_ms": ctx.get("updraft_velocity_ms", 2.5)
        }

        # Step 2 & 3 & 4: Parcel Ascent Thermodynamics, Köhler Activation, and DSD Spatial Evolution
        logger.info("Simulating parcel ascent thermodynamics and droplet size distribution (DSD) evolution...")
        simulator = CloudMicrophysicsSimulator(sim_config)
        
        # Yield control to event loop to preserve non-blocking async contract
        await asyncio.sleep(0)
        
        modeled_profile, growth_rates = simulator.run_simulation(ambient_profile, initial_dsd)

        # Step 5: Statistical Cross-Comparison with Empirical Observations
        logger.info("Performing statistical evaluation against empirical observation profiles...")
        comparison_matrix, performance_summary = ObservationalComparator.evaluate(
            modeled_profile=modeled_profile,
            observed_profile=observed_data
        )

        # Step 6: Compile Structured Analysis Report Output
        output_payload = {
            "status": "success",
            "microphysical_analysis_summary": {
                "simulation_parameters": sim_config,
                "performance_metrics": performance_summary,
                "cloud_base_altitude_m": modeled_profile[0]["altitude_m"] if modeled_profile else 0.0,
                "cloud_top_altitude_m": modeled_profile[-1]["altitude_m"] if modeled_profile else 0.0,
                "max_modeled_lwc_kg_m3": max((p["liquid_water_content_kg_m3"] for p in modeled_profile), default=0.0)
            },
            "theoretical_droplet_growth_rates": growth_rates,
            "modeled_cloud_profile": modeled_profile,
            "observed_vs_theoretical_comparison_matrix": comparison_matrix
        }

        logger.info("Cloud Droplet Microphysics Engine execution successfully completed.")
        return json.dumps(output_payload, indent=2)

    except Exception as e:
        error_msg = f"Error encountered during cloud microphysics engine execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({
            "status": "error",
            "error_details": error_msg
        }, indent=2)