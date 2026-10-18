"""AuraOne federated-learning participant SDK (P1-05).

Usage:

    from aura.federation import ParticipantClient, generate_keypair

    keypair = generate_keypair()
    # -> register keypair.public_pem + keypair.fingerprint with the
    #    coordinator (POST federations/[federationId]/participants)

    client = ParticipantClient(
        base_url="https://api.auraone.ai",
        org_id="<coordinator org>",
        api_key="ak_...",            # participant-scoped credential (P1-04)
        federation_id="fed_...",
        participant_id="part_...",
        private_key_pem=keypair.private_pem,
    )
    client.submit_update(
        round_id="round_...",
        vector=trained_parameters,      # from dp_sgd_train or your trainer
        sample_count=len(dataset),
    )
"""

from .participant import (
    COEFF_MOD_BIT_SIZES,
    DEFAULT_POLY_MODULUS_DEGREE,
    GLOBAL_SCALE_BITS,
    FederationClientError,
    FederationContext,
    ParticipantClient,
    ParticipantKeyPair,
    SubmittedUpdate,
    TrainingReport,
    build_ckks_context,
    dp_sgd_train,
    encrypt_vector_ckks,
    fingerprint_public_key,
    generate_keypair,
    load_private_key,
    load_public_key,
    public_pem_from_private,
    sha256_hex,
    sign_ciphertext_hash,
    signature_preimage,
)

__all__ = [
    "COEFF_MOD_BIT_SIZES",
    "DEFAULT_POLY_MODULUS_DEGREE",
    "GLOBAL_SCALE_BITS",
    "FederationClientError",
    "FederationContext",
    "ParticipantClient",
    "ParticipantKeyPair",
    "SubmittedUpdate",
    "TrainingReport",
    "build_ckks_context",
    "dp_sgd_train",
    "encrypt_vector_ckks",
    "fingerprint_public_key",
    "generate_keypair",
    "load_private_key",
    "load_public_key",
    "public_pem_from_private",
    "sha256_hex",
    "sign_ciphertext_hash",
    "signature_preimage",
]
