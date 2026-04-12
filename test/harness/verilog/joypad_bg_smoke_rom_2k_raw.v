module joypad_bg_smoke_rom_raw_2k(
    input wire CLK,
    input wire [10:0] CPU_ADDR,
    output reg [7:0] CPU_DATA
);
    (* ram_style = "block" *) reg [7:0] rom [0:1151];
    initial begin
`ifdef SYNTHESIS
        $readmemh("build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", rom);
`else
        integer mem_fd;
        mem_fd = $fopen("build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", "r");
        if (mem_fd != 0) begin
            $fclose(mem_fd);
            $readmemh("build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", rom);
        end else begin
            mem_fd = $fopen("../../../build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", "r");
            if (mem_fd != 0) begin
                $fclose(mem_fd);
                $readmemh("../../../build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", rom);
            end else begin
                mem_fd = $fopen("../../../../build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", "r");
                if (mem_fd != 0) begin
                    $fclose(mem_fd);
                    $readmemh("../../../../build/rom_verilator/test_hardware_soc_core_joypad_native/joypad_bg_smoke_rom_2k.mem", rom);
                end else begin
                    $error("joypad_bg_smoke_rom_2k.mem not found");
                end
            end
        end
`endif
    end

    always @(posedge CLK) begin
        CPU_DATA <= rom[CPU_ADDR];
    end
endmodule
