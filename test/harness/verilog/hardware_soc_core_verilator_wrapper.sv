module hardware_soc_core_verilator_wrapper (
    input clk_i,
    input rst_i,
    input rom_select_i,
    input [7:0] joypad_buttons_i,
    output [55:0] output__
);
    hardware_soc_core_verilator_top impl (
        .clk_i(clk_i),
        .rst_i(rst_i),
        .rom_select_i(rom_select_i),
        .joypad_buttons_i(joypad_buttons_i),
        .status_o(output__)
    );
endmodule
