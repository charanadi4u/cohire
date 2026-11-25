from dataclasses import dataclass
import hmac, asyncio
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings

bearer=HTTPBearer(auto_error=False)
@dataclass(frozen=True)
class Context:
    tenant: str
    actor: str
    scopes: frozenset[str]

def verify(token):
    s=settings()
    if s.dev_auth and hmac.compare_digest(token,s.dev_token):
        return Context(s.tenant_id,'local-recruiter',frozenset({'recruit','privacy','analytics','feedback'}))
    if not (s.oidc_jwks_url and s.oidc_issuer and s.oidc_audience): raise ValueError('AUTH_NOT_CONFIGURED')
    key=jwt.PyJWKClient(s.oidc_jwks_url).get_signing_key_from_jwt(token)
    c=jwt.decode(token,key.key,algorithms=['RS256'],issuer=s.oidc_issuer,audience=s.oidc_audience,
                 options={'require':['exp','iat','sub','tenant_id']})
    # tenant_id must be an issuer-controlled membership claim, never a user-editable claim.
    from uuid import UUID
    return Context(str(UUID(c['tenant_id'])),c['sub'],frozenset(c.get('scope','').split()))

async def context(credentials: HTTPAuthorizationCredentials | None=Depends(bearer)):
    try:
        if credentials is None: raise ValueError()
        return await asyncio.to_thread(verify,credentials.credentials)
    except Exception: raise HTTPException(401,'INVALID_CREDENTIALS') from None

def require(scope):
    async def dependency(ctx: Context=Depends(context)):
        if scope not in ctx.scopes: raise HTTPException(403,'INSUFFICIENT_SCOPE')
        return ctx
    return dependency
