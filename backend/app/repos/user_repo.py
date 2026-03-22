

async def get_users_by_type(db: AsyncSession, offset: int, limit: int, search: str = None, user_type: str = None):
    user_poly = with_polymorphic(User, [Admin, Student, Manager])
    query = select(user_poly)
    count_query = select(func.count()).select_from(user_poly)

    if user_type:
        query = query.filter(User.type == user_type)
        count_query = count_query.filter(User.type == user_type)

    if search is not None:
        terms = search.lower().split()
        if len(terms) > MAX_SEARCH_TERMS:
            raise TooManyRecordsException(max_amount=MAX_SEARCH_TERMS, loc=["query", "q"], input_=terms)
        filters = []

        for term in terms:
            like_term = f"%{term}%"
            filters.append(or_(
                User.name.ilike(like_term),
                User.second_name.ilike(like_term),
                User.surname.ilike(like_term),
                User.email.ilike(like_term),
                cast(Student.index_number, VARCHAR()).ilike(like_term),
            ))

        count_query = count_query.filter(*filters)
        query = query.filter(*filters)

    query = query.offset(offset).limit(limit)
    results = await db.execute(query)
    results = results.scalars().all()

    total_count = await db.scalar(count_query)

    return LimitedResponse(
        offset=offset,
        limit=limit,
        total_count=total_count,
        content=[*results]
    )
