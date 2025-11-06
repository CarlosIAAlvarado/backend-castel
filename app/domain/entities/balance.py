from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timezone


class Balance(BaseModel):
    """
    Entidad de dominio: Balance de cuenta de trading.

    Representa el balance (saldo) de una cuenta en un momento específico.
    Incluye validaciones de negocio para garantizar integridad de datos.
    """

    id: Optional[str] = Field(default=None, alias="_id")
    user_id_db: Optional[str] = Field(default=None, alias="agente_id")
    user_id: str = Field(alias="userId")
    account_id: Optional[str] = Field(default=None, alias="account_id")  # Agregado por migracion
    balance: float
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    # ==================== Validaciones de Dominio ====================

    @field_validator("balance")
    @classmethod
    def balance_must_be_non_negative(cls, v: float) -> float:
        """
        Validación de negocio: El balance no puede ser negativo.

        Regla de negocio: No se permite sobregiro (overdraft) en cuentas de trading.

        Args:
            v: Valor del balance

        Returns:
            float: Balance validado

        Raises:
            ValueError: Si el balance es negativo
        """
        if v < 0:
            raise ValueError(f"Balance cannot be negative: ${v:.2f}")
        return v

    @field_validator("user_id", "user_id_db")
    @classmethod
    def user_id_must_not_be_empty(cls, v: Optional[str]) -> Optional[str]:
        """
        Validación de negocio: El ID de usuario no puede estar vacío.

        Args:
            v: User ID (puede ser None para user_id_db)

        Returns:
            Optional[str]: User ID validado o None

        Raises:
            ValueError: Si el user ID está vacío (pero no None)
        """
        if v is None:
            return None
        if not v.strip():
            raise ValueError("User ID cannot be empty")
        return v.strip()

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamp_must_not_be_future(cls, v: datetime) -> datetime:
        """
        Validación de negocio: Las fechas no pueden ser futuras.

        Regla de negocio: Solo se registran balances históricos o actuales,
        nunca futuros.

        Args:
            v: Timestamp

        Returns:
            datetime: Timestamp validado

        Raises:
            ValueError: Si la fecha es futura
        """
        # Usar datetime aware con UTC para comparaciones consistentes
        now = datetime.now(timezone.utc)
        # Convertir v a aware si es naive (asumir UTC)
        v_aware = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
        if v_aware > now:
            raise ValueError(f"Timestamp cannot be in the future: {v_aware} > {now}")
        return v

    # ==================== Métodos de Dominio ====================

    class Config:
        populate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    def to_dict(self) -> dict:
        """
        Convierte la entidad a diccionario para persistencia.

        Returns:
            dict: Representación en diccionario
        """
        data = self.model_dump(by_alias=True)
        if data.get("_id"):
            data["_id"] = str(data["_id"])
        return data

    def is_sufficient_for_trade(self, trade_size: float) -> bool:
        """
        Lógica de dominio: Verifica si el balance es suficiente para un trade.

        Args:
            trade_size: Tamaño del trade en USD

        Returns:
            bool: True si el balance es suficiente

        Example:
            >>> balance = Balance(balance=10000, ...)
            >>> balance.is_sufficient_for_trade(5000)
            True
        """
        return self.balance >= trade_size

    def calculate_available_margin(self, used_margin: float) -> float:
        """
        Lógica de dominio: Calcula el margen disponible.

        Args:
            used_margin: Margen utilizado en posiciones abiertas

        Returns:
            float: Margen disponible

        Example:
            >>> balance = Balance(balance=10000, ...)
            >>> available = balance.calculate_available_margin(3000)
            >>> print(f"Available: ${available:.2f}")
        """
        return max(0.0, self.balance - used_margin)
