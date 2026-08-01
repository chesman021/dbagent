# dbagent


# Ejemplo de uso Response
respuesta ante caso de busqueda de usuario simulacion

def obtener_usuario(user_id: int):
    usuario = {
        "id": user_id,
        "nombre": "Carlos",
        "salario": Decimal("15500.50"),
        "creado_el": datetime.now(),
    }

    if not usuario:
        res = ApiResponse.error(
            message="Usuario no encontrado", status_code=status.HTTP_404_NOT_FOUND
        )
        return JSONResponse(content=res, status_code=res["status_code"])

    res = ApiResponse.success(data=usuario, message="Usuario obtenido con éxito")
    return JSONResponse(
        content=json.loads(ApiResponse.to_json(res)),
        status_code=res["status_code"],
    )
