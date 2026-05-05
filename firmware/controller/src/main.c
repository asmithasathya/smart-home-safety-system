/*
 * Copyright (c) 2019 Nordic Semiconductor ASA
 *
 * SPDX-License-Identifier: LicenseRef-Nordic-5-Clause
 */

/** @file
 *  @brief Nordic mesh light switch sample
 */
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <bluetooth/mesh/models.h>
#include <bluetooth/mesh/dk_prov.h>
#include <dk_buttons_and_leds.h>
#include "model_handler.h"

#define UART_INPUT_MAX_LEN 32
#define UART_READER_STACK_SIZE 1024
#define UART_READER_PRIORITY 7

static void uart_reader_thread(void *arg1, void *arg2, void *arg3)
{
	const struct device *uart_dev = DEVICE_DT_GET(DT_CHOSEN(zephyr_console));
	char line[UART_INPUT_MAX_LEN];
	size_t len = 0;
	unsigned char c;

	ARG_UNUSED(arg1);
	ARG_UNUSED(arg2);
	ARG_UNUSED(arg3);

	if (!device_is_ready(uart_dev)) {
		printk("UART reader unavailable\n");
		return;
	}

	printk("Press CLEAR ALERT, then enter the controller password in UART\n");

	while (1) {
		if (uart_poll_in(uart_dev, &c) != 0) {
			k_msleep(20);
			continue;
		}

		if (c == '\r' || c == '\n') {
			if (len == 0) {
				continue;
			}

			line[len] = '\0';
			printk("\nUART input received\n");
			controller_handle_uart_password(line);
			len = 0;
			continue;
		}

		if (c == '\b' || c == 0x7f) {
			if (len > 0) {
				len--;
			}
			continue;
		}

		if (len < (UART_INPUT_MAX_LEN - 1)) {
			line[len++] = (char)c;
		}
	}
}

K_THREAD_DEFINE(uart_reader_tid, UART_READER_STACK_SIZE, uart_reader_thread,
		NULL, NULL, NULL, UART_READER_PRIORITY, 0, 0);

static void bt_ready(int err)
{
	if (err) {
		printk("Bluetooth init failed (err %d)\n", err);
		return;
	}

	printk("Bluetooth initialized\n");

	err = dk_leds_init();
	if (err) {
		printk("Initializing LEDs failed (err %d)\n", err);
		return;
	}

	err = dk_buttons_init(NULL);
	if (err) {
		printk("Initializing buttons failed (err %d)\n", err);
		return;
	}

	err = bt_mesh_init(bt_mesh_dk_prov_init(), model_handler_init());
	if (err) {
		printk("Initializing mesh failed (err %d)\n", err);
		return;
	}

	if (IS_ENABLED(CONFIG_BT_MESH_LOW_POWER)) {
		bt_mesh_lpn_set(true);
	}

	if (IS_ENABLED(CONFIG_SETTINGS)) {
		settings_load();
	}

	/* This will be a no-op if settings_load() loaded provisioning info */
	bt_mesh_prov_enable(BT_MESH_PROV_ADV | BT_MESH_PROV_GATT);

	printk("Mesh initialized\n");
}

int main(void)
{
	int err;

	printk("Initializing...\n");

	err = bt_enable(bt_ready);
	if (err) {
		printk("Bluetooth init failed (err %d)\n", err);
	}

	return 0;
}
