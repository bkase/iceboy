module icebreaker_uart_rom_top_verilator_wrapper (
    input wire clk_i,
    input wire btn_n_i,
    input wire rx_i,
    input wire [7:0] joypad_buttons_i,
    output wire tx_o,
    output wire ledr_n_o,
    output wire ledg_n_o,
    output wire lcd_sck_o,
    output wire lcd_mosi_o,
    output wire lcd_cs_o,
    output wire lcd_dc_o,
    output wire lcd_res_o,
    output wire lcd_bl_o,
    output wire debug_gpio0_o,
    output wire debug_gpio1_o,
    output wire dbg_pc0_o,
    output wire dbg_pc1_o,
    output wire dbg_pc2_o,
    output wire dbg_pc3_o,
    output wire dbg_mce_o,
    output wire dbg_phase0_o,
    output wire dbg_phase1_o,
    output wire dbg_phase2_o
);
    wire btn_d_right = joypad_buttons_i[0];
    wire btn_d_left = joypad_buttons_i[1];
    wire btn_d_up = joypad_buttons_i[2];
    wire btn_d_down = joypad_buttons_i[3];
    wire dip_a = joypad_buttons_i[4];
    wire dip_b = joypad_buttons_i[5];
    wire dip_select = joypad_buttons_i[6];
    wire dip_start = joypad_buttons_i[7];

    icebreaker_uart_rom_top impl (
        .CLK(clk_i),
        .BTN_N(btn_n_i),
        .RX(rx_i),
        .BTN_D_UP(btn_d_up),
        .BTN_D_DOWN(btn_d_down),
        .BTN_D_LEFT(btn_d_left),
        .BTN_D_RIGHT(btn_d_right),
        .DIP_A(dip_a),
        .DIP_B(dip_b),
        .DIP_START(dip_start),
        .DIP_SELECT(dip_select),
        .TX(tx_o),
        .LEDR_N(ledr_n_o),
        .LEDG_N(ledg_n_o),
        .LCD_SCK(lcd_sck_o),
        .LCD_MOSI(lcd_mosi_o),
        .LCD_CS(lcd_cs_o),
        .LCD_DC(lcd_dc_o),
        .LCD_RES(lcd_res_o),
        .LCD_BL(lcd_bl_o),
        .DEBUG_GPIO0(debug_gpio0_o),
        .DEBUG_GPIO1(debug_gpio1_o),
        .DBG_PC0(dbg_pc0_o),
        .DBG_PC1(dbg_pc1_o),
        .DBG_PC2(dbg_pc2_o),
        .DBG_PC3(dbg_pc3_o),
        .DBG_MCE(dbg_mce_o),
        .DBG_PHASE0(dbg_phase0_o),
        .DBG_PHASE1(dbg_phase1_o),
        .DBG_PHASE2(dbg_phase2_o)
    );
endmodule
