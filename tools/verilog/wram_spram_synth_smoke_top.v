module wram_spram_synth_smoke_top(input wire clk);
    wire [59:0] output__;

    \iceboy::mem::phys::spram_test_top::wram_spram_test_top  dut (
        .clk_i_i(clk),
        .t_index_i_i(2'b00),
        .cpu_addr_i_i(13'h0000),
        .aux_addr_i_i(13'h0000),
        .write_en_i_i(1'b0),
        .write_addr_i_i(13'h0000),
        .write_data_i_i(8'h00),
        .output__(output__)
    );
endmodule
