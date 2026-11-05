#include "stm32f4xx_hal.h"

UART_HandleTypeDef huart2;

void MX_USART2_UART_Init(void) {
    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    HAL_UART_Init(&huart2);
}
