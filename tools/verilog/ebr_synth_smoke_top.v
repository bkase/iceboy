module ebr_synth_smoke_top(input wire clk);
    wire [23:0] output__;

    \iceboy::mem::phys::ebr_test_top::ebr_synth_test_top  dut (
        .clk_i(clk),
        .hram_cpu_addr_i_i(7'h00),
        .hram_dma_addr_i_i(7'h01),
        .hram_write_en_i_i(1'b0),
        .hram_write_addr_i_i(7'h00),
        .hram_write_data_i_i(8'h00),
        .oam_read_addr_i_i(8'h00),
        .oam_cpu_write_en_i_i(1'b0),
        .oam_cpu_write_addr_i_i(8'h00),
        .oam_cpu_write_data_i_i(8'h00),
        .oam_dma_write_en_i_i(1'b0),
        .oam_dma_write_addr_i_i(8'h00),
        .oam_dma_write_data_i_i(8'h00),
        .output__(output__)
    );
endmodule
