# Методы обнаружения бота

## Индикаторы компрометации (IoC)

| Индикатор | Что видит безопасник | Метод детекции |
|-----------|----------------------|----------------|
| Аномальный rate | 1 аккаунт читает 200+ статей/день | Rate limiting, anomaly detection |
| Один IP | Все запросы с одного VPS IP | IP reputation, ASN check |
| Нет mouse/scroll | Headless browser не генерирует human events | Behavioral analytics JS |
| Fake Googlebot | User-Agent Googlebot, но IP не в Google ASN | Reverse DNS verification |
| Нет JS execution | Запрос без выполнения JS | JS challenge / fingerprint |
| Паттерн времени | Идеально ровные интервалы между запросами | Timing analysis |

## Рекомендации по защите

- Server-side content gating (не отдавать контент в DOM без авторизации)
- Googlebot verification через reverse DNS
- Behavioral analytics (mouse movements, scroll depth)
- Rate limiting per account
- Блокировка datacenter IP ranges
- JS challenge (Datadome / PerimeterX)
