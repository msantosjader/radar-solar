from __future__ import annotations

from dataclasses import dataclass

from src.models import Usuario


PROFILE_TO_TIPO = {
    'customer': 'B2C',
    'company': 'B2B',
}

PROFILE_TO_HOME = {
    'customer': '/cliente/dashboard',
    'company': '/empresa/mapa',
}


@dataclass(frozen=True)
class AuthSession:
    usuario_id: int
    firebase_uid: str
    email: str
    nome: str
    profile: str
    tipo_perfil: str


def normalizar_profile(profile: str | None) -> str:
    if profile in PROFILE_TO_TIPO:
        return profile
    return 'customer'


def rota_inicial(profile: str | None) -> str:
    return PROFILE_TO_HOME[normalizar_profile(profile)]


def criar_ou_atualizar_usuario(firebase_uid: str, email: str, profile: str, nome: str | None = None) -> tuple[Usuario, bool]:
    profile = normalizar_profile(profile)
    tipo_perfil = PROFILE_TO_TIPO[profile]
    nome_base = (nome or '').strip() or email.split('@', 1)[0]

    usuario, created = Usuario.get_or_create(
        email=email,
        defaults={
            'firebase_uid': firebase_uid,
            'nome': nome_base,
            'tipo_perfil': tipo_perfil,
        },
    )

    updated = False
    if usuario.firebase_uid != firebase_uid:
        usuario.firebase_uid = firebase_uid
        updated = True
    if usuario.tipo_perfil != tipo_perfil:
        usuario.tipo_perfil = tipo_perfil
        updated = True
    if not usuario.nome and nome_base:
        usuario.nome = nome_base
        updated = True

    if updated:
        usuario.save()

    return usuario, created


def serializar_sessao(usuario: Usuario, profile: str) -> dict:
    profile = normalizar_profile(profile)
    return {
        'usuario_id': usuario.id,
        'firebase_uid': usuario.firebase_uid or '',
        'email': usuario.email,
        'nome': usuario.nome,
        'profile': profile,
        'tipo_perfil': usuario.tipo_perfil,
    }
