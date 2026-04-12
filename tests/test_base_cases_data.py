# Centralized source of truth for base test cases.

TEST_CASES = {
    "test_get_last_email": {
        "expected": "return wf.vars.emails[#wf.vars.emails]",
        "prompts": [
            "получить последний email из списка",
            "извлеки email, который находится последним в списке",
            "из всех писем в списке найди последнее",
            "найди такое письмо, которое находится в конце",
            "get the last email from the emails list"
        ]
    },
    "test_increment_counter": {
        "expected": "return wf.vars.tryCountN + 1",
        "prompts": [
            "увеличить счётчик попыток на 1",
            "добавь единицу к переменной tryCountN",
            "сделай инкремент для счётчика попыток",
            "увеличь tryCountN на один",
            "increment tryCountN by 1"
        ]
    },
    "test_create_empty_array": {
        "expected": "local result = _utils.array.new()\nreturn result",
        "prompts": [
            "создать новый пустой массив и вернуть его",
            "сделай новый массив и верни",
            "создай пустой список",
            "верни инициализированный пустой массив",
            "create a new empty array"
        ]
    },
    "test_filter_done_orders": {
        "expected": "local result = _utils.array.new()\nfor _, item in ipairs(wf.vars.orders) do\n  if item.status == \"done\" then\n    table.insert(result, item)\n  end\nend\nreturn result",
        "prompts": [
            "отфильтровать массив заказов, оставить только те, где status равен 'done'",
            "выбери из orders только выполненные (status == 'done')",
            "оставь в списке заказов только те записи, у которых статус done",
            "отбери из массива wf.vars.orders объекты со статусом done",
            "filter orders where status is done"
        ]
    },
    "test_sum_numbers": {
        "expected": "local total = 0\nfor _, v in ipairs(wf.vars.numbers) do\n  total = total + v\nend\nreturn total",
        "prompts": [
            "сложить все числа в массиве numbers",
            "посчитай сумму элементов в массиве numbers",
            "просуммируй все значения из списка чисел",
            "найди сумму элементов массива numbers",
            "sum all numbers in the numbers array"
        ]
    },
    "test_check_is_admin": {
        "expected": "return wf.vars.userRole == \"admin\"",
        "prompts": [
            "проверить, является ли пользователь администратором",
            "верни true если userRole равно 'admin'",
            "проверь роль пользователя на равенство 'admin'",
            "пользователь админ?",
            "check if userRole is admin"
        ]
    },
    "test_find_max_number": {
        "expected": "local max = wf.vars.numbers[1]\nfor _, v in ipairs(wf.vars.numbers) do\n  if v > max then\n    max = v\n  end\nend\nreturn max",
        "prompts": [
            "найти максимальное число в массиве",
            "верни наибольшее значение из списка numbers",
            "какое число самое большое в массиве numbers?",
            "определи максимум в списке чисел",
            "find the maximum number in the numbers array"
        ]
    },
    "test_count_elements": {
        "expected": "return #wf.vars.items",
        "prompts": [
            "подсчитать количество элементов в массиве items",
            "сколько элементов в списке items?",
            "узнай длину массива items",
            "верни размер массива items",
            "count the number of elements in the items array"
        ]
    },
    "test_get_first_element": {
        "expected": "return wf.vars.items[1]",
        "prompts": [
            "получить первый элемент массива",
            "верни самый первый элемент из списка items",
            "извлеки элемент массива, который идет первым",
            "отдай первый пункт из массива items",
            "get the first item from the array"
        ]
    },
    "test_check_array_empty": {
        "expected": "return #wf.vars.items == 0",
        "prompts": [
            "проверить, пустой ли массив",
            "массив items пуст?",
            "верни true если в списке нет элементов",
            "узнай, является ли список items пустым",
            "check if the items array is empty"
        ]
    }
}
