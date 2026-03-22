

@router.get("",
            dependencies=[Depends(RequireUser(UserType.ADMIN))],
            tags=["users"],
            response_model=LimitedResponse[Union[UserModel, StudentModel]],
            responses=None,
            status_code=status.HTTP_200_OK,
            summary="Get users",
            response_description="Successful Response")
async def get_users(
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=0, le=500),
        db: AsyncSession = Depends(get_db),
        query: str = Query(None, alias="q"),
        user_type: UserType = None
):
    """
    Get users. Users can be searched by filling the query param. \\
    User type can be added for additional filtering. \\
    Search terms are split by space. They can be: index_number, mail, name, surname or second_name. \\
    Checks if max search terms have not been exceeded, otherwise raises 422 Unprocessable.
    """
    return await user_repo.get_users_by_type(db, offset, limit, query, user_type)