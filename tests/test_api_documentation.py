"""Check the presentation contract without changing or exercising financial operations."""

from app.main import app


# Keep the Swagger-only walkthrough navigable with nested input and output contracts.
def test_swagger_flow_examples_and_response_schemas():
    """Reviewers can find the ordered steps, nested wearer fields and source evidence."""
    schema = app.openapi()
    assert schema["tags"][0]["name"] == "00 · Access"
    prepare = schema["paths"]["/sales/prepare"]["post"]
    assert "family" in prepare["requestBody"]["content"]["application/json"]["examples"]
    assert "WearerSelection" in schema["components"]["schemas"]
    assert prepare["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/QuoteResult")
    detail = schema["paths"]["/api/checkouts/{identifier}/detail"]["get"]
    assert detail["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/CheckoutEvidenceSchema")
    assert "transactions" in detail["description"]
    assert "login" in schema["info"]["description"]


# Ensure every documentation reference resolves so Swagger can render expanded schemas.
def test_openapi_references_resolve():
    """Nested response definitions must not leave broken component references."""
    schema = app.openapi()

    # Visit nested OpenAPI structures and resolve each local schema reference.
    def inspect(value):
        """Walk dictionaries and lists without making requests or mutating data."""
        if isinstance(value, dict):
            if "$ref" in value:
                target = schema
                for part in value["$ref"].removeprefix("#/").split("/"):
                    target = target[part]
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    inspect(schema)
