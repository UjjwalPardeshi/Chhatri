"""Provider-agnostic AI plumbing: the H26 label, the provider chain, the H16 untrusted-input wrapper.

The adapters, the free-tier data gate and the concrete chains live in `chhatri.integrations`. Nothing here
decides money (ADR 0001): a chain returns a reply or says why it could not.
"""
